import os
import smtplib
import requests
import akshare as ak
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ============ 1. 读取环境变量 ============
STOCK_LIST = os.environ.get("STOCK_LIST", "600519,000858")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.deepseek.com/v1")

EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.qq.com")

print(f"📧 收件邮箱: {EMAIL_TO}")
print(f"📤 发件邮箱: {EMAIL_USER}")
print(f"🖥️ SMTP服务器: {EMAIL_HOST}")
print(f"📊 分析股票: {STOCK_LIST}")

# ============ 2. 获取股票数据 ============
def get_stock_data(stock_code):
    """获取单只股票的近期数据"""
    try:
        # 获取最近30天日K线数据
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            adjust="qfq"
        )
        if df is None or len(df) == 0:
            return f"未获取到 {stock_code} 的数据"

        # 取最近10天数据
        recent = df.tail(10)
        
        info = f"\n【股票代码: {stock_code}】\n"
        info += f"最近交易日数据:\n"
        info += f"{'日期':<12} {'开盘':>10} {'收盘':>10} {'最高':>10} {'最低':>10} {'涨跌幅':>8} {'成交量':>12}\n"
        info += "-" * 80 + "\n"
        
        for _, row in recent.iterrows():
            date_str = str(row['日期'])[:10]
            open_price = row['开盘']
            close_price = row['收盘']
            high = row['最高']
            low = row['最低']
            change_pct = row.get('涨跌幅', 0)
            volume = row.get('成交量', 0)
            info += f"{date_str:<12} {open_price:>10.2f} {close_price:>10.2f} {high:>10.2f} {low:>10.2f} {change_pct:>7.2f}% {volume:>12,.0f}\n"
        
        # 计算简单技术指标
        closes = df['收盘'].values
        if len(closes) >= 5:
            ma5 = sum(closes[-5:]) / 5
            info += f"\n5日均线: {ma5:.2f}"
        if len(closes) >= 20:
            ma20 = sum(closes[-20:]) / 20
            info += f"\n20日均线: {ma20:.2f}"
        
        latest_close = closes[-1]
        info += f"\n最新收盘价: {latest_close:.2f}"
        
        return info
    except Exception as e:
        return f"获取 {stock_code} 数据失败: {e}"

# ============ 3. 调用 DeepSeek AI 分析 ============
def ai_analyze(stock_data_text):
    """调用大模型分析股票"""
    if not LLM_API_KEY:
        return "⚠️ 未配置 LLM_API_KEY，跳过AI分析"
    
    today = datetime.now().strftime("%Y年%m月%d日")
    
    prompt = f"""你是一位专业的A股投资分析师。今天是{today}，请根据以下股票数据进行简要分析，给出：
1. 短期趋势判断（看多/看空/震荡）
2. 关键技术位提示
3. 风险提示
4. 操作建议

请用通俗易懂的语言，不要太长，每只股票分析不超过200字。

股票数据如下：
{stock_data_text}

请按以下格式输出：
📈 **[股票代码] 分析报告**
- 短期趋势：xxx
- 关键技术位：xxx
- 风险提示：xxx
- 操作建议：xxx
"""

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 兼容不同API地址格式
    chat_url = LLM_API_URL.rstrip('/')
    if not chat_url.endswith('/chat/completions'):
        chat_url = chat_url + '/chat/completions'
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        print(f"🔄 正在调用AI分析，模型: {LLM_MODEL}，地址: {chat_url}")
        resp = requests.post(chat_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        print("✅ AI分析完成")
        return content
    except Exception as e:
        print(f"❌ AI分析失败: {e}")
        return f"⚠️ AI分析失败: {e}\n\n以下是原始数据供参考：\n{stock_data_text}"

# ============ 4. 发送邮件 ============
def send_email(subject, html_content):
    """通过SMTP发送邮件"""
    if not EMAIL_TO or not EMAIL_USER or not EMAIL_PASS:
        print("⚠️ 邮箱配置不完整，跳过发送邮件")
        print(f"  EMAIL_TO={'有' if EMAIL_TO else '无'}, EMAIL_USER={'有' if EMAIL_USER else '无'}, EMAIL_PASS={'有' if EMAIL_PASS else '无'}")
        return False
    
    # 确定SMTP端口
    if "qq.com" in EMAIL_HOST:
        port = 465
    elif "163.com" in EMAIL_HOST:
        port = 465
    elif "gmail.com" in EMAIL_HOST:
        port = 587
    elif "outlook.com" in EMAIL_HOST or "hotmail.com" in EMAIL_HOST:
        port = 587
    else:
        port = 465
    
    print(f"📧 正在发送邮件到 {EMAIL_TO}，端口 {port}")
    
    # 构建邮件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    
    # 纯文本版本
    text_part = MIMEText(html_content, "plain", "utf-8")
    msg.attach(text_part)
    
    # HTML版本（更好看）
    html_body = f"""
    <html>
    <body style="font-family: 'Microsoft YaHei', Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
    <h2 style="color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px;">📈 {subject}</h2>
    <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.8; color: #333;">
{html_content}
    </div>
    <hr style="border: none; border-top: 1px solid #ddd; margin-top: 20px;">
    <p style="color: #999; font-size: 12px; text-align: center;">本报告由 GitHub Actions + DeepSeek AI 自动生成<br>仅供参考，不构成投资建议</p>
    </div>
    </body>
    </html>
    """
    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)
    
    try:
        if port == 465:
            # SSL加密
            server = smtplib.SMTP_SSL(EMAIL_HOST, port, timeout=30)
        else:
            # TLS加密
            server = smtplib.SMTP(EMAIL_HOST, port, timeout=30)
            server.starttls()
        
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())
        server.quit()
        print("✅ 邮件发送成功！")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

# ============ 5. 主流程 ============
def main():
    print("=" * 60)
    print(f"🚀 开始运行股票分析报告")
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    stocks = [s.strip() for s in STOCK_LIST.split(",") if s.strip()]
    
    # 获取所有股票数据
    all_data = ""
    for code in stocks:
        print(f"\n📊 获取 {code} 数据中...")
        data = get_stock_data(code)
        all_data += data + "\n"
    
    print("\n" + "=" * 60)
    print("🤖 正在调用AI分析...")
    print("=" * 60)
    
    # AI分析
    analysis = ai_analyze(all_data)
    
    # 组装最终报告
    today = datetime.now().strftime("%Y年%m月%d日")
    report = f"""
{'='*50}
📈 股票分析报告
📅 日期：{today}
{'='*50}

{analysis}

{'='*50}
📊 原始数据
{'='*50}
{all_data}

⚠️ 本报告由AI自动生成，仅供参考，不构成投资建议。
"""
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)
    
    # 发送邮件
    send_email(f"📈 {today} 股票分析报告", report)
    
    print("\n✅ 全部流程完成！")

if __name__ == "__main__":
    main()
