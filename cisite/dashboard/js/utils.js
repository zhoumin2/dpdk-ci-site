/**
 * Create a toast that an error occurred and log the error to the console
 * @param {Object} e Any object related to the error.
 */
export const errorPopup = e => {
  const message = "An error occurred. Please refresh the page and try again. If this persists, please email dpdklab@iol.unh.edu.";
  toastr.error(message);
  console.error(e);
  logError(e);
}

/**
 * Check if the response was "ok". If not, show the error popup.
 * @param {!Response} response The Response to a Request.
 * @return {boolean} if the response was ok.
 */
export const handleResponse = response => {
  if (!response.ok) {
    errorPopup(response);
  }
  return response.ok;
}
