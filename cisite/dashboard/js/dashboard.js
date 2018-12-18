class Dashboard {
  constructor() {
    const table = document.getElementById('dashboard-table');
    for (let i = table.dataset.start; i < table.dataset.end; i++) {
      this.getAndAddRow(i, table);
    }
  }

  /**
   * Fetch the row from the server, and replace the placeholders
   * @param {number} offset
   * @param {HTMLTableSectionElement} table
   */
  getAndAddRow(offset, table) {
    const tr = document.getElementById('row-' + offset);
    fetch('row/' + offset + '/').then(response => {
      response.text().then(text => {
        if (response.ok) {
            tr.innerHTML = text;
        } else {
            tr.innerHTML = '<td></td><td>Error getting patch information:<br>' + text + '</td>';
            logError(response);
        }
      });
    }).catch(e => {
      tr.innerHTML = '<td></td><td>Error getting patch information:<br>' + e.response.data + '</td>';
      logError(e);
    });
  }
}

window.onload = () => {
  new Dashboard();
}
