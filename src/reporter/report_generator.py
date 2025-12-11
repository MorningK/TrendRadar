# coding=utf-8
"""报告生成模块"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from ..utils.file_utils import clean_title, html_escape, ensure_directory_exists
from ..utils.time_utils import format_time_filename, get_beijing_time
from ..utils.file_utils import get_output_path


def prepare_report_data(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
) -> Dict:
    """准备报告数据"""
    processed_new_titles = []

    # 在增量模式下隐藏新增新闻区域
    hide_new_section = mode == "incremental"

    # 只有在非隐藏模式下才处理新增新闻部分
    if not hide_new_section:
        filtered_new_titles = {}
        if new_titles and id_to_name:
            from ..analyzer.data_processor import load_frequency_words
            from ..analyzer.statistics_calculator import matches_word_groups
            word_groups, filter_words, global_filters = load_frequency_words()
            for source_id, titles_data in new_titles.items():
                filtered_titles = {}
                for title, title_data in titles_data.items():
                    if matches_word_groups(title, word_groups, filter_words, global_filters):
                        filtered_titles[title] = title_data
                if filtered_titles:
                    filtered_new_titles[source_id] = filtered_titles

        if filtered_new_titles and id_to_name:
            for source_id, titles_data in filtered_new_titles.items():
                source_name = id_to_name.get(source_id, source_id)
                source_titles = []

                for title, title_data in titles_data.items():
                    url = title_data.get("url", "")
                    mobile_url = title_data.get("mobileUrl", "")
                    ranks = title_data.get("ranks", [])

                    processed_title = {
                        "title": title,
                        "source_name": source_name,
                        "time_display": "",
                        "count": 1,
                        "ranks": ranks,
                        "rank_threshold": 10,  # 默认值
                        "url": url,
                        "mobile_url": mobile_url,
                        "is_new": True,
                    }
                    source_titles.append(processed_title)

                if source_titles:
                    processed_new_titles.append(
                        {
                            "source_id": source_id,
                            "source_name": source_name,
                            "titles": source_titles,
                        }
                    )

    processed_stats = []
    for stat in stats:
        if stat["count"] <= 0:
            continue

        processed_titles = []
        for title_data in stat["titles"]:
            processed_title = {
                "title": title_data["title"],
                "source_name": title_data["source_name"],
                "time_display": title_data["time_display"],
                "count": title_data["count"],
                "ranks": title_data["ranks"],
                "rank_threshold": title_data["rank_threshold"],
                "url": title_data.get("url", ""),
                "mobile_url": title_data.get("mobileUrl", ""),
                "is_new": title_data.get("is_new", False),
            }
            processed_titles.append(processed_title)

        processed_stats.append(
            {
                "word": stat["word"],
                "count": stat["count"],
                "percentage": stat.get("percentage", 0),
                "titles": processed_titles,
            }
        )

    return {
        "stats": processed_stats,
        "new_titles": processed_new_titles,
        "failed_ids": failed_ids or [],
        "total_new_count": sum(
            len(source["titles"]) for source in processed_new_titles
        ),
    }


def format_title_for_platform(
    platform: str, title_data: Dict, show_source: bool = True
) -> str:
    """统一的标题格式化方法"""
    from ..analyzer.statistics_calculator import format_rank_display
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform
    )

    link_url = title_data["mobile_url"] or title_data["url"]

    cleaned_title = clean_title(title_data["title"])

    if platform == "feishu":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']}次)</font>"

        return result

    elif platform == "dingtalk":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    elif platform in ("wework", "bark"):
        # WeWork 和 Bark 使用 markdown 格式
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    elif platform == "telegram":
        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}次)</code>"

        return result

    elif platform == "ntfy":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}次)`"

        return result

    elif platform == "slack":
        # Slack 使用 mrkdwn 格式
        if link_url:
            # Slack 链接格式: <url|text>
            formatted_title = f"<{link_url}|{cleaned_title}>"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        # 排名（使用 * 加粗）
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "slack"
        )
        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}次)`"

        return result

    elif platform == "html":
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html"
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'[{escaped_source_name}] <a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = (
                f'[{escaped_source_name}] <span class="no-link">{escaped_title}</span>'
            )

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}次)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    else:
        return cleaned_title


def generate_html_report(
    stats: List[Dict],
    total_titles: int,
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    is_daily_summary: bool = False,
    update_info: Optional[Dict] = None,
) -> str:
    """生成HTML报告"""
    if is_daily_summary:
        if mode == "current":
            filename = "当前榜单汇总.html"
        elif mode == "incremental":
            filename = "当日增量.html"
        else:
            filename = "当日汇总.html"
    else:
        filename = f"{format_time_filename()}.html"

    file_path = get_output_path("html", filename)

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)

    html_content = render_html_content(
        report_data, total_titles, is_daily_summary, mode, update_info
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if is_daily_summary:
        # 生成到根目录（供 GitHub Pages 访问）
        root_index_path = Path("index.html")
        with open(root_index_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 同时生成到 output 目录（供 Docker Volume 挂载访问）
        output_index_path = Path("output") / "index.html"
        ensure_directory_exists("output")
        with open(output_index_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    return file_path


def render_html_content(
    report_data: Dict,
    total_titles: int,
    is_daily_summary: bool = False,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
) -> str:
    """渲染HTML内容"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>热点新闻分析</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==\" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                margin: 0; 
                padding: 16px; 
                background: #fafafa;
                color: #333;
                line-height: 1.5;
            }
            
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 16px rgba(0,0,0,0.06);
            }
            
            .header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 32px 24px;
                text-align: center;
                position: relative;
            }
            
            .save-buttons {
                position: absolute;
                top: 16px;
                right: 16px;
                display: flex;
                gap: 8px;
            }
            
            .save-btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                white-space: nowrap;
            }
            
            .save-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-1px);
            }
            
            .save-btn:active {
                transform: translateY(0);
            }
            
            .save-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            
            .header-title {
                font-size: 22px;
                font-weight: 700;
                margin: 0 0 20px 0;
            }
            
            .header-info {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                font-size: 14px;
                opacity: 0.95;
            }
            
            .info-item {
                text-align: center;
            }
            
            .info-label {
                display: block;
                font-size: 12px;
                opacity: 0.8;
                margin-bottom: 4px;
            }
            
            .info-value {
                font-weight: 600;
                font-size: 16px;
            }
            
            .content {
                padding: 24px;
            }
            
            .word-group {
                margin-bottom: 40px;
            }
            
            .word-group:first-child {
                margin-top: 0;
            }
            
            .word-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            
            .word-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .word-name {
                font-size: 17px;
                font-weight: 600;
                color: #1a1a1a;
            }
            
            .word-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }
            
            .word-count.hot { color: #dc2626; font-weight: 600; }
            .word-count.warm { color: #ea580c; font-weight: 600; }
            
            .word-index {
                color: #999;
                font-size: 12px;
            }
            
            .news-item {
                margin-bottom: 20px;
                padding: 16px 0;
                border-bottom: 1px solid #f5f5f5;
                position: relative;
                display: flex;
                gap: 12px;
                align-items: center;
            }
            
            .news-item:last-child {
                border-bottom: none;
            }
            
            .news-item.new::after {
                content: "NEW";
                position: absolute;
                top: 12px;
                right: 0;
                background: #fbbf24;
                color: #92400e;
                font-size: 9px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 4px;
                letter-spacing: 0.5px;
            }
            
            .news-number {
                color: #999;
                font-size: 13px;
                font-weight: 600;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                align-self: flex-start;
                margin-top: 8px;
            }
            
            .news-content {
                flex: 1;
                min-width: 0;
                padding-right: 40px;
            }
            
            .news-item.new .news-content {
                padding-right: 50px;
            }
            
            .news-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
                flex-wrap: wrap;
            }
            
            .source-name {
                color: #666;
                font-size: 12px;
                font-weight: 500;
            }
            
            .rank-num {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 10px;
                min-width: 18px;
                text-align: center;
            }
            
            .rank-num.top { background: #dc2626; }
            .rank-num.high { background: #ea580c; }
            
            .time-info {
                color: #999;
                font-size: 11px;
            }
            
            .count-info {
                color: #059669;
                font-size: 11px;
                font-weight: 500;
            }
            
            .news-title {
                font-size: 15px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }
            
            .news-link {
                color: #2563eb;
                text-decoration: none;
            }
            
            .news-link:hover {
                text-decoration: underline;
            }
            
            .news-link:visited {
                color: #7c3aed;
            }
            
            .new-section {
                margin-top: 40px;
                padding-top: 24px;
                border-top: 2px solid #f0f0f0;
            }
            
            .new-section-title {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                margin: 0 0 20px 0;
            }
            
            .new-source-group {
                margin-bottom: 24px;
            }
            
            .new-source-title {
                font-size: 14px;
                font-weight: 600;
                color: #444;
                margin-bottom: 12px;
            }
            
            .new-news-item {
                margin-bottom: 16px;
                padding-bottom: 16px;
                border-bottom: 1px solid #f5f5f5;
            }
            
            .new-news-item:last-child {
                border-bottom: none;
            }
            
            .failed-section {
                margin-top: 40px;
                padding-top: 24px;
                border-top: 2px solid #f0f0f0;
            }
            
            .failed-title {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                margin: 0 0 20px 0;
            }
            
            .failed-list {
                display: grid;
                gap: 8px;
            }
            
            .failed-item {
                padding: 12px;
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                color: #dc2626;
                font-size: 14px;
            }
            
            .update-info {
                margin-top: 24px;
                padding: 16px;
                background: #fefce8;
                border: 1px solid #f59e0b;
                border-radius: 8px;
                text-align: center;
            }
            
            .update-title {
                font-weight: 600;
                color: #d97706;
                margin-bottom: 8px;
            }
            
            .update-content {
                font-size: 14px;
                color: #92400e;
            }
            
            .update-link {
                display: inline-block;
                margin-top: 8px;
                color: #d97706;
                text-decoration: underline;
            }
            
            .empty-state {
                text-align: center;
                padding: 40px 20px;
                color: #9ca3af;
            }
            
            .empty-icon {
                font-size: 48px;
                margin-bottom: 16px;
            }
            
            .empty-text {
                font-size: 16px;
                margin: 0;
            }
            
            @media (max-width: 640px) {
                body {
                    padding: 8px;
                }
                
                .header {
                    padding: 24px 16px;
                }
                
                .header-title {
                    font-size: 18px;
                }
                
                .header-info {
                    grid-template-columns: 1fr;
                    gap: 12px;
                }
                
                .content {
                    padding: 16px;
                }
                
                .word-header {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 8px;
                }
                
                .word-info {
                    align-self: stretch;
                }
                
                .word-name {
                    font-size: 16px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="save-buttons">
                    <button class="save-btn" onclick="saveAsImage()">保存图片</button>
                    <button class="save-btn" onclick="saveAsPDF()">保存PDF</button>
                </div>
                <h1 class="header-title">热点新闻分析</h1>
                <div class="header-info">
                    <div class="info-item">
                        <span class="info-label">分析时间</span>
                        <span class="info-value">""" + get_beijing_time().strftime("%m-%d %H:%M") + """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">新闻总数</span>
                        <span class="info-value">""" + str(total_titles) + """</span>
                    </div>
                </div>
            </div>
            
            <div class="content">
    """

    # 添加更新信息
    if update_info:
        html += f"""
                <div class="update-info">
                    <div class="update-title">发现新版本</div>
                    <div class="update-content">
                        当前版本: {update_info['current_version']} → 最新版本: {update_info['remote_version']}
                    </div>
                    <a href="https://github.com/302ai/trendradar" class="update-link" target="_blank">前往GitHub查看更新</a>
                </div>
        """

    # 添加新增新闻部分
    if report_data["new_titles"]:
        html += """
                <div class="new-section">
                    <h2 class="new-section-title">🆕 新增新闻</h2>
        """
        for source_group in report_data["new_titles"]:
            html += f"""
                    <div class="new-source-group">
                        <div class="new-source-title">[{source_group['source_name']}]</div>
            """
            for title_data in source_group["titles"]:
                title_html = format_title_for_platform("html", title_data, show_source=False)
                html += f"""
                        <div class="new-news-item">{title_html}</div>
                """
            html += """
                    </div>
            """
        html += """
                </div>
        """

    # 添加统计数据
    if report_data["stats"]:
        for i, stat in enumerate(report_data["stats"]):
            word_count_class = "hot" if stat["count"] > 10 else ("warm" if stat["count"] > 5 else "")
            html += f"""
                <div class="word-group">
                    <div class="word-header">
                        <div class="word-info">
                            <span class="word-name">{stat['word']}</span>
                            <span class="word-count {word_count_class}">{stat['count']} 条 ({stat['percentage']}%)</span>
                        </div>
                        <span class="word-index">#{i+1}</span>
                    </div>
            """
            
            for j, title_data in enumerate(stat["titles"]):
                title_html = format_title_for_platform("html", title_data)
                is_new_class = " new" if title_data.get("is_new") else ""
                html += f"""
                    <div class="news-item{is_new_class}">
                        <div class="news-number">{j+1}</div>
                        <div class="news-content">
                            {title_html}
                        </div>
                    </div>
                """
            
            html += """
                </div>
            """
    else:
        html += """
                <div class="empty-state">
                    <div class="empty-icon">📰</div>
                    <p class="empty-text">暂无匹配的新闻数据</p>
                </div>
        """

    # 添加失败ID列表
    if report_data["failed_ids"]:
        html += """
                <div class="failed-section">
                    <h2 class="failed-title">❌ 请求失败</h2>
                    <div class="failed-list">
        """
        for failed_id in report_data["failed_ids"]:
            html += f"""
                        <div class="failed-item">{failed_id}</div>
            """
        html += """
                    </div>
                </div>
        """

    html += """
            </div>
        </div>
        
        <script>
            function saveAsImage() {
                const saveBtn = document.querySelector('.save-btn[onclick="saveAsImage()"]');
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';
                
                html2canvas(document.querySelector('.container')).then(canvas => {
                    const link = document.createElement('a');
                    link.download = 'trendradar_report.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                    
                    saveBtn.disabled = false;
                    saveBtn.textContent = '保存图片';
                }).catch(err => {
                    console.error('保存图片失败:', err);
                    saveBtn.disabled = false;
                    saveBtn.textContent = '保存图片';
                });
            }
            
            function saveAsPDF() {
                alert('PDF保存功能需要额外的库支持，当前环境不支持。请使用浏览器的打印功能（Ctrl+P）并选择保存为PDF。');
            }
        </script>
    </body>
    </html>
    """

    return html