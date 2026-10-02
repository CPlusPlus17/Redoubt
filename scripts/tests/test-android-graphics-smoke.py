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


if __name__ == "__main__":
    unittest.main()
