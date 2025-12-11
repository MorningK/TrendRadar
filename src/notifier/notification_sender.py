# coding=utf-8
"""通知推送模块"""

import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, List, Optional
from ..config.config_manager import parse_multi_account_config, validate_paired_configs, limit_accounts, get_account_at_index
from ..utils.push_record_manager import PushRecordManager


def send_to_notifications(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到所有通知渠道"""
    from ..config.config_manager import load_config
    CONFIG = load_config()
    
    # 初始化推送管理器
    push_manager = PushRecordManager()
    
    # 检查推送窗口设置
    if CONFIG["PUSH_WINDOW"]["ENABLED"]:
        start_time = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["START"]
        end_time = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["END"]
        
        if not push_manager.is_in_time_range(start_time, end_time):
            print(f"推送窗口检查：当前时间不在 {start_time}-{end_time} 范围内，跳过推送")
            return
        
        if CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"]:
            if push_manager.has_pushed_today():
                print("推送窗口检查：今天已推送过，跳过推送")
                return
    
    # 记录推送
    push_manager.record_push(report_type)
    
    print(f"正在发送 {report_type} 通知...")
    
    # 飞书推送
    if CONFIG["FEISHU_WEBHOOK_URL"]:
        send_to_feishu(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )
    
    # 钉钉推送
    if CONFIG["DINGTALK_WEBHOOK_URL"]:
        send_to_dingtalk(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )
    
    # 企业微信推送
    if CONFIG["WEWORK_WEBHOOK_URL"]:
        send_to_wework(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )
    
    # Telegram推送
    if CONFIG["TELEGRAM_BOT_TOKEN"] and CONFIG["TELEGRAM_CHAT_ID"]:
        send_to_telegram(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )
    
    # 邮件推送
    if CONFIG["EMAIL_FROM"] and CONFIG["EMAIL_PASSWORD"] and CONFIG["EMAIL_TO"]:
        send_to_email(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            mode,
            html_file_path,
        )
    
    # ntfy推送
    if CONFIG["NTFY_SERVER_URL"] and CONFIG["NTFY_TOPIC"]:
        send_to_ntfy(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )
    
    # Bark推送
    if CONFIG["BARK_URL"]:
        send_to_bark(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )
    
    # Slack推送
    if CONFIG["SLACK_WEBHOOK_URL"]:
        send_to_slack(
            stats,
            failed_ids,
            report_type,
            new_titles,
            id_to_name,
            update_info,
            proxy_url,
            mode,
            html_file_path,
        )


def send_to_feishu(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到飞书"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    webhook_urls = parse_multi_account_config(CONFIG["FEISHU_WEBHOOK_URL"])
    webhook_urls = limit_accounts(webhook_urls, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"], "飞书")
    
    if not webhook_urls:
        return
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title, title_data in titles_data.items():
                title_content = format_title_for_platform("feishu", {**title_data, "title": title, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("feishu", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 发送消息
    headers = {"Content-Type": "application/json; charset=utf-8"}
    msg_type = CONFIG.get("FEISHU_MSG_TYPE", "text")
    
    # 打印配置变量，方便调试
    print(f"飞书推送配置：")
    print(f"  - FEISHU_WEBHOOK_URL: {CONFIG['FEISHU_WEBHOOK_URL']}")
    print(f"  - FEISHU_MSG_TYPE: {msg_type}")
    print(f"  - webhook_urls: {webhook_urls}")
    print(f"  - 消息长度: {len(content)} 字符")
    print(f"  - 消息开头: {content[:100]}...")
    
    for i, webhook_url in enumerate(webhook_urls):
        if not webhook_url:
            continue
            
        try:
            # 检查webhook_url格式
            if not webhook_url.startswith('https://'):
                print(f"  - 警告: webhook_url格式不正确: {webhook_url}")
            
            # 使用main_backup.py中的飞书推送格式
            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True,
                        "enable_forward": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"📰 {report_type}报告"
                        },
                        "template": "blue"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": content
                            }
                        }
                    ]
                }
            }
            
            print(f"  - 准备发送到账号 {i+1}: {webhook_url[:50]}...")
            response = requests.post(webhook_url, headers=headers, json=message, timeout=10)
            response.raise_for_status()
            print(f"飞书推送成功 (账号 {i+1}/{len(webhook_urls)})")
            print(f"  - 响应状态: {response.status_code}")
            print(f"  - 响应内容: {response.text}")
        except Exception as e:
            print(f"飞书推送失败 (账号 {i+1}/{len(webhook_urls)}): {e}")
            # 打印响应内容，方便调试
            if hasattr(response, 'text'):
                print(f"  - 响应状态: {response.status_code}")
                print(f"  - 响应内容: {response.text}")
            # 打印完整的请求消息，方便调试
            print(f"  - 请求消息: {json.dumps(message, ensure_ascii=False, indent=2)[:500]}...")


def send_to_dingtalk(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到钉钉"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    webhook_urls = parse_multi_account_config(CONFIG["DINGTALK_WEBHOOK_URL"])
    webhook_urls = limit_accounts(webhook_urls, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"], "钉钉")
    
    if not webhook_urls:
        return
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("dingtalk", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("dingtalk", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 发送消息
    headers = {"Content-Type": "application/json; charset=utf-8"}
    message = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    
    for i, webhook_url in enumerate(webhook_urls):
        if not webhook_url:
            continue
            
        try:
            response = requests.post(webhook_url, headers=headers, json=message, timeout=10)
            response.raise_for_status()
            print(f"钉钉推送成功 (账号 {i+1}/{len(webhook_urls)})")
        except Exception as e:
            print(f"钉钉推送失败 (账号 {i+1}/{len(webhook_urls)}): {e}")


def send_to_wework(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到企业微信"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    webhook_urls = parse_multi_account_config(CONFIG["WEWORK_WEBHOOK_URL"])
    webhook_urls = limit_accounts(webhook_urls, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"], "企业微信")
    
    if not webhook_urls:
        return
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("wework", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("wework", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 发送消息
    headers = {"Content-Type": "application/json; charset=utf-8"}
    
    msg_type = CONFIG.get("WEWORK_MSG_TYPE", "markdown")
    if msg_type == "markdown":
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": content.replace("\n", "\n\n")  # 企业微信markdown需要双换行
            }
        }
    else:
        message = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
    
    for i, webhook_url in enumerate(webhook_urls):
        if not webhook_url:
            continue
            
        try:
            response = requests.post(webhook_url, headers=headers, json=message, timeout=10)
            response.raise_for_status()
            print(f"企业微信推送成功 (账号 {i+1}/{len(webhook_urls)})")
        except Exception as e:
            print(f"企业微信推送失败 (账号 {i+1}/{len(webhook_urls)}): {e}")


def send_to_telegram(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到Telegram"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    bot_tokens = parse_multi_account_config(CONFIG["TELEGRAM_BOT_TOKEN"])
    chat_ids = parse_multi_account_config(CONFIG["TELEGRAM_CHAT_ID"])
    
    # 验证配对配置
    configs = {"bot_token": bot_tokens, "chat_id": chat_ids}
    valid, count = validate_paired_configs(configs, "Telegram", required_keys=["bot_token", "chat_id"])
    if not valid or count == 0:
        return
    
    count = min(count, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"])
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("telegram", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("telegram", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 发送消息
    for i in range(count):
        bot_token = get_account_at_index(bot_tokens, i)
        chat_id = get_account_at_index(chat_ids, i)
        
        if not bot_token or not chat_id:
            continue
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": content,
            "parse_mode": "HTML"
        }
        
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            response = requests.post(url, json=payload, timeout=10, proxies=proxies)
            response.raise_for_status()
            print(f"Telegram推送成功 (账号 {i+1}/{count})")
        except Exception as e:
            print(f"Telegram推送失败 (账号 {i+1}/{count}): {e}")


def send_to_email(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到邮件"""
    from ..config.config_manager import load_config, SMTP_CONFIGS
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    from_addr = CONFIG["EMAIL_FROM"]
    password = CONFIG["EMAIL_PASSWORD"]
    to_addrs = parse_multi_account_config(CONFIG["EMAIL_TO"], ",")
    
    if not from_addr or not password or not to_addrs:
        return
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("email", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("email", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 构建邮件
    msg = MIMEMultipart()
    msg['From'] = Header(f"TrendRadar <{from_addr}>", 'utf-8')
    msg['To'] = Header(', '.join(to_addrs), 'utf-8')
    msg['Subject'] = Header(f"📰 {report_type}报告", 'utf-8')
    
    msg.attach(MIMEText(content, 'plain', 'utf-8'))
    
    # 获取SMTP配置
    domain = from_addr.split('@')[-1]
    smtp_config = SMTP_CONFIGS.get(domain, SMTP_CONFIGS["qq.com"])  # 默认使用QQ邮箱配置
    
    try:
        if smtp_config["encryption"] == "SSL":
            server = smtplib.SMTP_SSL(smtp_config["server"], smtp_config["port"])
        else:
            server = smtplib.SMTP(smtp_config["server"], smtp_config["port"])
            server.starttls()
        
        server.login(from_addr, password)
        
        for to_addr in to_addrs:
            server.sendmail(from_addr, to_addr, msg.as_string())
        
        server.quit()
        print(f"邮件推送成功，收件人: {', '.join(to_addrs)}")
    except Exception as e:
        print(f"邮件推送失败: {e}")


def send_to_ntfy(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到ntfy"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    topics = parse_multi_account_config(CONFIG["NTFY_TOPIC"])
    tokens = parse_multi_account_config(CONFIG["NTFY_TOKEN"])
    
    # 验证配置
    if tokens:
        configs = {"topic": topics, "token": tokens}
        valid, count = validate_paired_configs(configs, "ntfy")
        if not valid or count == 0:
            return
        count = min(count, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"])
    else:
        count = min(len(topics), CONFIG["MAX_ACCOUNTS_PER_CHANNEL"])
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("ntfy", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("ntfy", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 发送消息
    for i in range(count):
        topic = get_account_at_index(topics, i)
        token = get_account_at_index(tokens, i)
        
        if not topic:
            continue
        
        url = f"{CONFIG['NTFY_SERVER_URL']}/{topic}"
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            response = requests.post(url, data=content.encode('utf-8'), headers=headers, timeout=10, proxies=proxies)
            response.raise_for_status()
            print(f"ntfy推送成功 (话题 {i+1}/{count}): {topic}")
        except Exception as e:
            print(f"ntfy推送失败 (话题 {i+1}/{count}): {e}")


def send_to_bark(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到Bark"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    bark_urls = parse_multi_account_config(CONFIG["BARK_URL"])
    bark_urls = limit_accounts(bark_urls, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"], "Bark")
    
    if not bark_urls:
        return
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("bark", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("bark", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # 发送消息
    for i, bark_url in enumerate(bark_urls):
        if not bark_url:
            continue
            
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            response = requests.post(bark_url, json={"title": f"📰 {report_type}报告", "body": content}, timeout=10, proxies=proxies)
            response.raise_for_status()
            print(f"Bark推送成功 (账号 {i+1}/{len(bark_urls)})")
        except Exception as e:
            print(f"Bark推送失败 (账号 {i+1}/{len(bark_urls)}): {e}")


def send_to_slack(
    stats: List[Dict],
    failed_ids: List,
    report_type: str,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
):
    """发送到Slack"""
    from ..config.config_manager import load_config
    from ..reporter.report_generator import format_title_for_platform
    CONFIG = load_config()
    
    webhook_urls = parse_multi_account_config(CONFIG["SLACK_WEBHOOK_URL"])
    webhook_urls = limit_accounts(webhook_urls, CONFIG["MAX_ACCOUNTS_PER_CHANNEL"], "Slack")
    
    if not webhook_urls:
        return
    
    content = f"📰 {report_type}报告\n\n"
    
    # 添加更新信息
    if update_info:
        content += f"🆕 发现新版本: {update_info['current_version']} → {update_info['remote_version']}\n\n"
    
    # 添加新增新闻
    if new_titles and mode != "incremental":
        content += "🆕 新增新闻:\n"
        for source_id, titles_data in new_titles.items():
            source_name = id_to_name.get(source_id, source_id) if id_to_name else source_id
            for title_data in titles_data.values():
                title_content = format_title_for_platform("slack", {**title_data, "source_name": source_name}, show_source=False)
                content += f"  • {title_content}\n"
        content += "\n"
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] > 0:
            content += f"🏷️ {stat['word']} ({stat['count']}条)\n"
            for title_data in stat["titles"][:5]:  # 限制显示前5条
                title_content = format_title_for_platform("slack", title_data)
                content += f"  • {title_content}\n"
            content += "\n"
    
    # 添加失败信息
    if failed_ids:
        content += f"❌ 请求失败: {', '.join(failed_ids)}\n"
    
    content += f"\n📊 共 {sum(stat['count'] for stat in stats)} 条匹配新闻"
    
    # Slack消息格式
    message = {
        "text": content
    }
    
    # 发送消息
    headers = {"Content-Type": "application/json"}
    for i, webhook_url in enumerate(webhook_urls):
        if not webhook_url:
            continue
            
        try:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            response = requests.post(webhook_url, headers=headers, json=message, timeout=10, proxies=proxies)
            response.raise_for_status()
            print(f"Slack推送成功 (账号 {i+1}/{len(webhook_urls)})")
        except Exception as e:
            print(f"Slack推送失败 (账号 {i+1}/{len(webhook_urls)}): {e}")