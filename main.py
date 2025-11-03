import os
import subprocess
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.OpenAction import OpenAction


class RipgrepExtension(Extension):
    def __init__(self):
        super(RipgrepExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or ""
        print(f"[DEBUG] Query received: {query}")

        if not query.strip():
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Please enter a search query',
                    description='Example: rg main',
                )
            ])

        try:
            # 获取用户设置的 search_path，如果没有设置则默认家目录
            search_path = extension.preferences.get('search_path', "~")

            # 展开 ~ 为绝对路径
            search_path = os.path.expanduser(search_path)

            # 调用 ripgrep 搜索，-n 显示行号，--no-heading 不显示文件头
            cmd = ["rg", "--no-heading", "-n", "--color", "never", query, search_path]
            print(f"[DEBUG] Running command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            output = result.stdout.strip()
            print(f"[DEBUG] ripgrep output:\n{output}")

            if not output:
                return RenderResultListAction([
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name='No results found',
                        description=f'Keywords: {query}'
                    )
                ])

            # 显示前 10 条匹配结果
            results = []
            for line in output.splitlines()[:10]:
                # ripgrep 输出格式: 文件路径:行号:匹配内容
                try:
                    path, line_no, content = line.split(":", 2)
                except ValueError:
                    continue

                # 点击条目直接打开文件并跳到匹配行
                uri = f"file://{os.path.abspath(path)}"
                open_action = OpenAction(uri)

                results.append(
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name=os.path.abspath(path) + f":{line_no}",  # 显示全路径 + 行号
                        description=content.strip(),
                        on_enter=open_action
                    )
                )


            return RenderResultListAction(results)

        except Exception as e:
            print(f"[ERROR] Exception occurred: {e}")
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/error.png',
                    name='Error occurred',
                    description=str(e)
                )
            ])


if __name__ == '__main__':
    RipgrepExtension().run()
