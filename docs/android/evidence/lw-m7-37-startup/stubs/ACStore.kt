package mozilla.components.browser.state.store
import kotlinx.coroutines.flow.StateFlow
import mozilla.components.browser.state.action.BrowserAction
import mozilla.components.browser.state.state.BrowserState
class BrowserStore { val stateFlow: StateFlow<BrowserState> get() = error("stub"); fun dispatch(action: BrowserAction) {} }
