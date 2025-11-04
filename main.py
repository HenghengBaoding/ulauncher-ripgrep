import os
import shlex
import subprocess
import threading
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.OpenAction import OpenAction

MAX_RESULTS = 10  # 最大显示匹配结果数

class RipgrepExtension(Extension):
    def __init__(self):
        super(RipgrepExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or ""
        query = query.strip()
        if not query:
            keyword = extension.preferences.get('rg', 'rg')
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Please enter a search query',
                    description=f'Example: {keyword} main',
                )
            ])

        # 创建线程异步执行搜索
        results_container = []
        search_thread = threading.Thread(
            target=self.run_multiline_search,
            args=(query, extension, results_container)
        )
        search_thread.start()
        search_thread.join()  # 等待完成，也可以改为不 join 实现完全异步

        return RenderResultListAction(results_container if results_container else [
            ExtensionResultItem(
                icon='images/icon.png',
                name='No results found',
                description=f'Keywords: {query}'
            )
        ])

    def _get_search_paths(self, raw_search_path):
        """
        将 raw_search_path （字符串）解析为路径列表。
        支持：
          - 多路径以空格分隔
          - 使用引号包裹包含空格的路径
        返回绝对路径列表（不存在的路径仍会被返回，rg 会忽略它们）
        """
        if not raw_search_path or not raw_search_path.strip():
            raw_search_path = "~"
        # 使用 shlex.split 支持引号
        parts = shlex.split(raw_search_path)
        paths = []
        for p in parts:
            expanded = os.path.expanduser(p)
            abs_path = os.path.abspath(expanded)
            paths.append(abs_path)
        return paths

    def run_multiline_search(self, query, extension, results_container):
        # 从首选项读取原始 search_path 字符串，支持多路径（空格分隔 / 支持引号）
        raw_search_path = extension.preferences.get('search_path', "~")
        search_paths = self._get_search_paths(raw_search_path)

        # 如果没有任何 path，使用家目录
        if not search_paths:
            search_paths = [os.path.abspath(os.path.expanduser("~"))]

        query_lines = query.splitlines()
        if not query_lines:
            return

        # 第1步：搜索第一行（把多个 search_paths 作为命令的多个参数）
        first_line = query_lines[0]
        try:
            initial_cmd = [
                "rg", "--fixed-strings", "--no-heading", "-n", "--color", "never",
                first_line
            ] + search_paths  # rg 可以接受多个 path 参数
            result = subprocess.run(initial_cmd, capture_output=True, text=True)
            output = result.stdout.strip()
        except Exception:
            return

        if not output:
            return

        # 解析第一行搜索结果
        matches = []
        for line in output.splitlines():
            try:
                path, line_no, _ = line.split(":", 2)
                matches.append({
                    "path": os.path.abspath(path),
                    "line_no": int(line_no)
                })
            except ValueError:
                continue

        # 第2步及以后：逐行过滤
        for i in range(1, len(query_lines)):
            line_text = query_lines[i]
            new_matches = []
            for match in matches:
                try:
                    start_line = match["line_no"] + i - 1
                    with open(match["path"], "r", encoding="utf-8", errors="ignore") as f:
                        # 跳过 start_line-1 行
                        for _ in range(start_line):
                            next(f, None)
                        line = next(f, "").rstrip("\n").rstrip("\r")
                        # 为兼容代码缩进/空格差异，比较时也可以 strip()
                        if line == line_text or line.strip() == line_text.strip():
                            new_matches.append(match)
                except Exception:
                    continue
            if not new_matches:
                return
            matches = new_matches

        # 显示前 MAX_RESULTS 条匹配
        for match in matches[:MAX_RESULTS]:
            try:
                block_lines = []
                start_line = match["line_no"] - 1
                with open(match["path"], "r", encoding="utf-8", errors="ignore") as f:
                    for _ in range(start_line):
                        next(f, None)
                    for _ in range(len(query_lines)):
                        line = next(f, "").rstrip("\n").rstrip("\r")
                        block_lines.append(line)
                results_container.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=f"{match['path']}:{match['line_no']}",
                        description="\n".join(block_lines),
                        on_enter=OpenAction(f"file://{match['path']}")
                    )
                )
            except Exception:
                continue


if __name__ == '__main__':
    RipgrepExtension().run()
