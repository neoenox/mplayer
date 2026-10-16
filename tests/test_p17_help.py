"""P17: ヘルプ (ショートカット一覧) ダイアログの検証。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import check, finish, make_app, patch_message_boxes

import main as app_main
from main import (HELP_NOTES, MOUSE_HELP, SHORTCUTS, HelpDialog, PlayerWindow,
                  build_help_html)


def main():
    patch_message_boxes()

    check("ショートカットが十分ある", len(SHORTCUTS) >= 8, f"{len(SHORTCUTS)}")
    keys = [k for k, _ in SHORTCUTS]
    for expected in ("Ctrl+O", "Space", "M", "S", "Esc", "F1"):
        check(f"ショートカット {expected} を掲載", expected in keys)
    check("全画面 (F / F11) を掲載",
          any("F11" in k for k in keys), f"{keys}")
    check("前後の動画 (Ctrl+←/→) を掲載",
          any("Ctrl+" in k and ("←" in k or "→" in k) for k in keys))
    check("マウス操作を掲載", len(MOUSE_HELP) >= 2)

    html = build_help_html()
    check("HTML にアプリ名", app_main.APP_NAME in html)
    check("HTML にバージョン", app_main.__version__ in html)
    for k, v in list(SHORTCUTS) + list(MOUSE_HELP):
        check(f"HTML に {k} の記載", k in html and v in html)
    for note in HELP_NOTES:
        check("HTML にヒント", note in html)

    make_app()
    w = PlayerWindow()
    check("ヘルプメニューにアクション", w.help_act.text() == "ショートカット一覧")
    check("F1 が割当", w.help_act.shortcut().toString() == "F1",
          w.help_act.shortcut().toString())

    check("初期状態はダイアログ未生成", w._help_dialog is None)

    w.show_shortcuts()
    dlg = w._help_dialog
    check("ダイアログが生成される", isinstance(dlg, HelpDialog))
    check("非モーダル (テストが止まらない)", dlg.isModal() is False)
    check("表示される", dlg.isVisible())
    text = dlg.browser.toPlainText()
    check("本文にショートカットが入る", "Space" in text and "Esc" in text)
    check("本文にヒントが入る", HELP_NOTES[0][:12] in text)
    check("タイトルが設定される", "ヘルプ" in dlg.windowTitle())

    first = dlg
    w.show_shortcuts()
    check("2回目は同じダイアログを再利用", w._help_dialog is first)

    dlg.close()
    check("閉じられる", not dlg.isVisible())
    w.close()
    return finish("P17help")


if __name__ == "__main__":
    sys.exit(main())
