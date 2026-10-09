document.querySelector("#token-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = document.querySelector("#token").value;
  await chrome.storage.session.set({ token });
  document.querySelector("#token").value = "";
  document.querySelector("#status").textContent = "Token guardado para esta sesion.";
});
