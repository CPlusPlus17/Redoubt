package mozilla.components.browser.state.action
sealed class BrowserAction
sealed class EngineAction : BrowserAction() { object PurgeHistoryAction : EngineAction() }
sealed class RecentlyClosedAction : BrowserAction() { object RemoveAllClosedTabAction : RecentlyClosedAction() }
