class Dashboard {
  constructor() {
    const table = document.getElementById('dashboard-table');
    const start = parseInt(table.dataset.start)
    const end = parseInt(table.dataset.end)
    const limit = parseInt(table.dataset.limit)
    for (let i = start; i < end; i += limit) {
      this.getAndAddRow(i, table, limit);
    }
  }

  /**
   * Fetch the row from the server, and replace the placeholders
   * @param {number} offset
   * @param {HTMLTableSectionElement} table
   */
  getAndAddRow(offset, table, limit) {
    let emptyRows = [];
    for (let i = offset; i < offset + limit; i++) {
      let element = document.getElementById(`row-${i}`);
      if (element) {
        emptyRows.push(element);
      }
    }
    fetch(`row/${offset}/?limit=${limit}`).then(response => {
      response.text().then(text => {
        if (response.ok) {
          // put text into html element to utilize dom api
          const temp = document.createElement('div');
          temp.innerHTML = text;
          // table -> tbody -> tr
          const rows = temp.children[0].children[0].children;
          // there is a possible race condition where the active patchsets change after
          // the initial request. This also accounts for when the limit ends up greater
          // than the offset.
          if (rows.length >= emptyRows.length) {
            for (let i = 0; i < emptyRows.length; i++) {
              emptyRows[i].innerHTML = rows[i].innerHTML;
            }
          } else {
            for (let i = 0; i < rows.length; i++) {
              emptyRows[i].innerHTML = rows[i].innerHTML;
            }
            const rest = emptyRows.length - rows.length;
            for (let i = 0; i < rest; i++) {
              emptyRows[i + rows.length].innerHTML = '<td></td><td>This patch has become inactive at the time of requesting.</td>';
            }
          }
        } else {
          for (let i = 0; i < emptyRows.length; i++) {
            emptyRows[i].innerHTML = `<td></td><td>Error getting patch information:<br>${text}</td>`;
          }
          logError(response);
        }
      });
    }).catch(e => {
      let text = `Error getting patch information:<br>${e}`;
      // Happens when changing pages during a fetch in Firefox. Ignore it.
      if (e.message === 'NetworkError when attempting to fetch resource.') {
        text = '<br><br>';
      } else {
        logError(e);
      }
      for (let i = 0; i < emptyRows.length; i++) {
        emptyRows[i].innerHTML = `<td></td><td>${text}</td>`;
      }
    });
  }
}

window.onload = () => {
  new Dashboard();
}
