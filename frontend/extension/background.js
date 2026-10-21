// Clicking the toolbar icon opens the side panel. We open it ourselves rather
// than with setPanelBehavior({ openPanelOnActionClick: true }), because only an
// action click that reaches onClicked grants activeTab, which lets "Use this
// job page" read the current tab on sites beyond LinkedIn and Indeed.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: false })
  .catch((error) => console.error(error))

chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId }).catch((error) => console.error(error))
})
