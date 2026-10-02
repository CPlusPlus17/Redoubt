#!/usr/bin/env python3
"""Offline tests for the graphics harness's Fenix UI selectors.

Fixtures are reduced uiautomator hierarchies with the attributes the selectors
read; the Compose menu item mirrors the rc2 dump (content-desc set, text empty).
"""
from pathlib import Path
import importlib.util
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("lw_graphics_ui", ROOT / "scripts/android-graphics-smoke.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

PKG = "org.redoubtbrowser"


def node(text="", desc="", bounds="[0,0][100,50]", rid="", cls="android.view.View", **extra):
    attrs = dict({"text": text, "content-desc": desc, "bounds": bounds, "resource-id": rid,
                  "class": cls, "package": PKG, "enabled": "true", "visible-to-user": "true"}, **extra)
    return "<node " + " ".join('%s="%s"' % item for item in attrs.items()) + "/>"


def hierarchy(*nodes):
    return "<?xml version='1.0' encoding='UTF-8'?><hierarchy rotation=\"0\">" + "".join(nodes) + "</hierarchy>"


def ubo_notice(package=PKG):
    child = lambda name, cls, text, clickable: (
        '<node resource-id="%s:id/%s" class="%s" text="%s" package="%s" clickable="%s" '
        'checkable="false" enabled="true" bounds="[10,10][90,40]"/>' % (package, name, cls, text, package, clickable))
    return ('<node class="android.widget.RelativeLayout" package="%s" enabled="true" bounds="[0,0][1080,600]">' % package
            + child("icon", "android.widget.ImageView", "", "false")
            + child("title", "android.widget.TextView", g.UBO_ADDED_TITLE, "false")
            + child("description", "android.widget.TextView", g.UBO_ADDED_DESCRIPTION, "false")
            + child("confirm_button", "android.widget.Button", "OK", "true")
            + "</node>")


class MenuItemTests(unittest.TestCase):
    def test_compose_item_is_found_by_content_desc(self):
        xml = hierarchy(node(desc="New tab", bounds="[0,0][300,100]"),
                        node(desc="New private tab", bounds="[0,100][300,200]"))
        found = g.menu_item(xml, "New private tab", PKG)
        self.assertEqual(found["content-desc"], "New private tab")
        self.assertEqual(found["centre"], (150, 150))

    def test_view_item_is_still_found_by_text(self):
        xml = hierarchy(node(text="Close tab", bounds="[0,0][300,100]"))
        self.assertEqual(g.menu_item(xml, "Close tab", PKG)["text"], "Close tab")

    def test_one_node_with_both_labels_counts_once(self):
        xml = hierarchy(node(text="New private tab", desc="New private tab"))
        self.assertIsNotNone(g.menu_item(xml, "New private tab", PKG))

    def test_different_nodes_by_text_and_desc_are_ambiguous(self):
        xml = hierarchy(node(text="New private tab", bounds="[0,0][300,100]"),
                        node(desc="New private tab", bounds="[0,100][300,200]"))
        with self.assertRaises(g.Failure):
            g.menu_item(xml, "New private tab", PKG)

    def test_absent_hidden_or_foreign_items_are_not_selected(self):
        self.assertIsNone(g.menu_item(hierarchy(node(desc="New tab")), "New private tab", PKG))
        hidden = node(desc="New private tab", **{"visible-to-user": "false"})
        self.assertIsNone(g.menu_item(hierarchy(hidden), "New private tab", PKG))
        foreign = node(desc="New private tab").replace(PKG, "com.android.systemui")
        self.assertIsNone(g.menu_item(hierarchy(foreign), "New private tab", PKG))


class EmptyPrivateHomeTests(unittest.TestCase):
    # Reduced from the rc2 dump after "Close tab" closed the last private tab.
    URL_BOX = node(desc="Search or enter address", rid="ADDRESSBAR_URL_BOX", bounds="[180,84][807,210]")

    def counter(self, label):
        return node(desc=label + " Tap to switch tabs.", rid="TabCounterTestTags.tabCounter",
                    bounds="[860,116][923,179]")

    def test_private_home_with_no_tabs_is_recognized(self):
        xml = hierarchy(node(text="Private browsing"), self.URL_BOX, self.counter("Private Tabs Open: 0."))
        self.assertTrue(g.empty_private_home(xml, PKG))

    def test_open_private_or_normal_tabs_are_not_the_empty_private_home(self):
        for label in ("Private Tabs Open: 1.", "Non-private Tabs Open: 0.", "Non-private Tabs Open: 2."):
            self.assertFalse(g.empty_private_home(hierarchy(self.URL_BOX, self.counter(label)), PKG))

    def test_counter_without_an_address_bar_is_not_enough(self):
        self.assertFalse(g.empty_private_home(hierarchy(self.counter("Private Tabs Open: 0.")), PKG))


class UboNoticeTests(unittest.TestCase):
    def test_notice_ok_is_recognized_and_present(self):
        xml = hierarchy(ubo_notice())
        button = g.ubo_added_notice(xml, PKG)
        self.assertEqual(button["resource-id"], PKG + ":id/confirm_button")
        self.assertTrue(g.ubo_added_notice_present(xml, PKG))

    def test_generic_ok_is_not_the_notice(self):
        xml = hierarchy(node(text="OK", cls="android.widget.Button", rid=PKG + ":id/confirm_button"))
        self.assertIsNone(g.ubo_added_notice(xml, PKG))
        self.assertFalse(g.ubo_added_notice_present(xml, PKG))

    def test_partial_sheet_still_counts_as_present(self):
        title = node(text=g.UBO_ADDED_TITLE, rid=PKG + ":id/title", cls="android.widget.TextView")
        xml = hierarchy(title)
        self.assertIsNone(g.ubo_added_notice(xml, PKG))
        self.assertTrue(g.ubo_added_notice_present(xml, PKG))


def window(index, name, uid, region, visible="true", flags="0x81800008", wtype="0x00000001"):
    return ("      %d: name='%s', displayId=0, portalToDisplayId=-1, paused=false, hasFocus=false, "
            "hasWallpaper=false, visible=%s, canReceiveKeys=false, flags=%s, type=%s, frame=[0,0][1080,1920], "
            "globalScale=1.000000, windowScale=(1.000000,1.000000), touchableRegion=%s, "
            "inputFeatures=0x00000000, ownerPid=1, ownerUid=%d, dispatchingTimeout=5000ms"
            % (index, name, visible, flags, wtype, region, uid))


APP = "Window{5fe3040 u0 %s/%s.App}" % (PKG, PKG)
STATUS = window(0, "Window{43b7e08 u0 StatusBar}", 10121, "[0,0][1080,63]", wtype="0x000007d0")
# Reduced from the rc2 private-tab capture: the IME window is still visible and
# touchable over the bottom of the screen while IMMS reports mInputShown=false.
STUCK_IME = window(1, "Window{8e8c063 u0 InputMethod}", 10106, "[0,1145][1080,1920]",
                   flags="0x81800108", wtype="0x000007db")
APP_WINDOW = window(2, APP, 10132, "[0,0][1080,1920]", flags="0x81012120")
SURFACE = window(3, "SurfaceView - %s/%s.App#0" % (PKG, PKG), 10132, "<empty>", flags="0x00000020",
                 wtype="0x00000000")


def dumpsys_input(*windows, anr=None):
    text = "INPUT MANAGER (dumpsys input)\n\nInput Dispatcher State:\n  Display: 0\n    Windows:\n"
    text += "\n".join(windows) + "\n  Global monitors in display 0:\n"
    if anr:
        text += "\nInput Dispatcher State at time of last ANR:\n  Display: 0\n    Windows:\n" + "\n".join(anr) + "\n"
    return text


REVIEW = (946, 1805)   # centre of the rc2 snackbar_action "Review"


class InputWindowTests(unittest.TestCase):
    def test_live_windows_are_parsed_topmost_first(self):
        windows = g.input_windows(dumpsys_input(STATUS, STUCK_IME, APP_WINDOW, SURFACE))
        self.assertEqual([w["ownerUid"] for w in windows], [10121, 10106, 10132, 10132])
        self.assertEqual(windows[1]["type"], g.TYPE_INPUT_METHOD)
        self.assertEqual(windows[1]["touchable"], [(0, 1145, 1080, 1920)])
        self.assertEqual(windows[3]["touchable"], [])

    def test_stale_anr_copy_is_ignored(self):
        text = dumpsys_input(STATUS, APP_WINDOW, anr=[STATUS, STUCK_IME, APP_WINDOW])
        self.assertIsNone(g.soft_keyboard_window(text))
        self.assertEqual(g.windows_covering(text, *REVIEW, PKG), [])

    def test_stuck_keyboard_covers_the_review_action(self):
        text = dumpsys_input(STATUS, STUCK_IME, APP_WINDOW, SURFACE)
        covering = g.windows_covering(text, *REVIEW, PKG)
        self.assertEqual([w["name"] for w in covering], ["Window{8e8c063 u0 InputMethod}"])
        self.assertIsNotNone(g.soft_keyboard_window(text))
        # The toolbar above the keyboard is still reached directly.
        self.assertEqual(g.windows_covering(text, 556, 148, PKG), [])

    def test_hidden_or_untouchable_windows_do_not_cover(self):
        hidden = window(1, "Window{1 u0 InputMethod}", 10106, "[0,1145][1080,1920]", visible="false",
                        wtype="0x000007db")
        untouchable = window(1, "Window{2 u0 Overlay}", 10200, "[0,0][1080,1920]", flags="0x00000018")
        for over in (hidden, untouchable):
            text = dumpsys_input(STATUS, over, APP_WINDOW)
            self.assertEqual(g.windows_covering(text, *REVIEW, PKG), [])
        self.assertIsNone(g.soft_keyboard_window(dumpsys_input(STATUS, hidden, APP_WINDOW)))

    def test_own_popup_does_not_count_as_covering(self):
        popup = window(1, "PopupWindow:1234", 10132, "[0,1000][1080,1920]")
        text = dumpsys_input(STATUS, popup, APP_WINDOW)
        self.assertEqual(g.windows_covering(text, *REVIEW, PKG), [])

    def test_status_bar_covers_the_top_strip(self):
        text = dumpsys_input(STATUS, APP_WINDOW)
        self.assertEqual([w["name"] for w in g.windows_covering(text, 500, 30, PKG)],
                         ["Window{43b7e08 u0 StatusBar}"])

    def test_missing_app_window_or_list_fails(self):
        with self.assertRaises(g.Failure):
            g.windows_covering(dumpsys_input(STATUS, STUCK_IME), *REVIEW, PKG)
        with self.assertRaises(g.Failure):
            g.input_windows("INPUT MANAGER (dumpsys input)\n")


class FakeEvidence:
    def __init__(self):
        self.events = []

    def event(self, name, data):
        self.events.append((name, data))


class FakeUI(g.UI):
    """UI with a scripted device: dumpsys input answers change after force-stop."""

    def __init__(self, before, after, ime="com.android.inputmethod.latin/.LatinIME", ime_uid=10106):
        self.package, self.evidence, self.timeout = PKG, FakeEvidence(), 5
        self.before, self.after, self.ime, self.ime_uid = before, after, ime, ime_uid
        self.commands, self.stopped = [], False

    def shell(self, *args, timeout=30):
        self.commands.append(args)
        if args[:2] == ("dumpsys", "input"):
            return self.after if self.stopped else self.before
        if args[:3] == ("settings", "get", "secure"):
            return self.ime + "\n"
        if args[:3] == ("pm", "list", "packages"):
            return "package:%s uid:%d\n" % (args[-1], self.ime_uid)
        if args[:2] == ("am", "force-stop"):
            self.stopped = True
            return ""
        if args[:2] == ("input", "tap"):
            return ""
        raise AssertionError("unexpected shell command %r" % (args,))


class KeyboardGuardTests(unittest.TestCase):
    stuck = dumpsys_input(STATUS, STUCK_IME, APP_WINDOW, SURFACE)
    clear = dumpsys_input(STATUS, APP_WINDOW, SURFACE)

    def test_no_keyboard_means_no_action(self):
        ui = FakeUI(self.clear, self.clear)
        ui.close_soft_keyboard("test", grace=0)
        self.assertFalse(ui.stopped)
        self.assertEqual(ui.evidence.events, [])

    def test_stuck_keyboard_is_force_stopped_and_recorded(self):
        ui = FakeUI(self.stuck, self.clear)
        ui.close_soft_keyboard("after private URL submission", grace=0)
        self.assertIn(("am", "force-stop", "com.android.inputmethod.latin"), ui.commands)
        name, data = ui.evidence.events[-1]
        self.assertEqual(name, "soft-keyboard-closed")
        self.assertEqual(data["window"], "Window{8e8c063 u0 InputMethod}")
        self.assertEqual(data["touchable"], [(0, 1145, 1080, 1920)])

    def test_keyboard_owned_by_another_package_is_not_stopped(self):
        ui = FakeUI(self.stuck, self.clear, ime_uid=10999)
        with self.assertRaises(g.Failure):
            ui.close_soft_keyboard("test", grace=0)
        self.assertFalse(ui.stopped)

    def test_the_app_itself_is_never_stopped_as_the_ime(self):
        ui = FakeUI(self.stuck, self.clear, ime=PKG + "/.Ime")
        with self.assertRaises(g.Failure):
            ui.close_soft_keyboard("test", grace=0)
        self.assertFalse(ui.stopped)

    def test_keyboard_that_survives_the_stop_fails(self):
        ui = FakeUI(self.stuck, self.stuck)
        ui_time = g.time.monotonic
        try:
            clock = iter(range(0, 1000, 10))
            g.time.monotonic = lambda: next(clock)
            with self.assertRaises(g.Failure):
                ui.close_soft_keyboard("test", grace=0)
        finally:
            g.time.monotonic = ui_time

    def test_tap_through_stuck_keyboard_closes_it_first(self):
        ui = FakeUI(self.stuck, self.clear)
        ui.tap({"centre": REVIEW, "resource-id": PKG + ":id/snackbar_action", "text": "Review"}, "quiet-review")
        stop = ui.commands.index(("am", "force-stop", "com.android.inputmethod.latin"))
        tap = ui.commands.index(("input", "tap", 946, 1805))
        self.assertLess(stop, tap)
        self.assertEqual([name for name, _ in ui.evidence.events], ["soft-keyboard-closed", "ui-action"])

    def test_tap_onto_another_overlay_fails_without_tapping(self):
        overlay = window(1, "Window{9 u0 SomeOverlay}", 10200, "[0,1000][1080,1920]")
        text = dumpsys_input(STATUS, overlay, APP_WINDOW)
        ui = FakeUI(text, text)
        with self.assertRaises(g.Failure):
            ui.tap({"centre": REVIEW}, "quiet-review")
        self.assertNotIn(("input", "tap", 946, 1805), ui.commands)
        self.assertFalse(ui.stopped)

    def test_clear_screen_taps_directly(self):
        ui = FakeUI(self.clear, self.clear)
        ui.tap({"centre": REVIEW}, "quiet-review")
        self.assertIn(("input", "tap", 946, 1805), ui.commands)
        self.assertFalse(ui.stopped)


class ScriptedReviewUI(g.UI):
    """Plays back uiautomator dumps after the Review tap."""

    def __init__(self, dumps):
        self.package, self.evidence, self.timeout = PKG, FakeEvidence(), 5
        self.review_results, self.dumps, self.taps = [], list(dumps), []

    def dump(self, label="ui", screenshot=False):
        return self.dumps.pop(0) if len(self.dumps) > 1 else self.dumps[0]

    def tap(self, node, label, long=False):
        self.taps.append(label)


SNACKBAR = node(text="Review", rid=PKG + ":id/snackbar_action", cls="android.widget.Button",
                bounds="[854,1742][1038,1868]")
LIST = node(rid=PKG + ":id/origin_permissions_dialog_list", cls="android.widget.LinearLayout",
            bounds="[100,500][980,1400]")
PAGE = node(text="Graphics acceptance fixture", bounds="[6,248][291,275]")


class QuietReviewTests(unittest.TestCase):
    def setUp(self):
        self.clock = iter(range(0, 10000))
        self.saved = g.time.monotonic, g.time.sleep
        g.time.monotonic = lambda: next(self.clock)
        g.time.sleep = lambda _seconds: None

    def tearDown(self):
        g.time.monotonic, g.time.sleep = self.saved

    def notice(self):
        return g.select_node(hierarchy(SNACKBAR), text="Review", package=PKG)

    def test_review_that_opens_the_list_is_recorded(self):
        ui = ScriptedReviewUI([hierarchy(PAGE), hierarchy(PAGE, LIST)])
        self.assertTrue(ui.quiet_review(self.notice(), private=True))
        self.assertEqual(ui.review_results, [{"private": True, "opened": True}])

    def test_expired_notice_falls_back_and_is_recorded(self):
        ui = ScriptedReviewUI([hierarchy(PAGE)])
        self.assertFalse(ui.quiet_review(self.notice(), private=False))
        self.assertEqual(ui.review_results, [{"private": False, "opened": False}])
        self.assertIn("fallback", ui.evidence.events[-1][1])

    def test_notice_still_shown_after_the_tap_is_a_failure(self):
        ui = ScriptedReviewUI([hierarchy(PAGE, SNACKBAR)])
        with self.assertRaises(g.Failure):
            ui.quiet_review(self.notice(), private=True)

    def test_other_permission_ui_after_the_tap_is_a_failure(self):
        entry = node(rid=PKG + ":id/origin_permissions_entry", bounds="[0,1400][1080,1500]")
        ui = ScriptedReviewUI([hierarchy(PAGE, entry)])
        with self.assertRaises(g.Failure):
            ui.quiet_review(self.notice(), private=True)


if __name__ == "__main__":
    unittest.main()
