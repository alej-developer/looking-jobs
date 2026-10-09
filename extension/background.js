chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== "get-token") {
    return false;
  }
  chrome.storage.session.get("token").then((data) => {
    sendResponse({ token: data.token || "" });
  });
  return true;
});
