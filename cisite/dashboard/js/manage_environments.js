class ManageEnvironments {
  constructor() {
    // replace the "Choose a file" label
    $('.custom-file-input').on('change', function() {
      $(this).next('.custom-file-label').html($(this)[0].files[0].name);
    })

    this.connect();
  }

  connect() {
    const socket = new WebSocket('ws://' + window.location.host + '/ws/manage-environment/');

    socket.onmessage = e => {
      const data = JSON.parse(e.data);
      switch (data.type) {
        case 'current': {
          this.setCurrent(data.message);
          break;
        }
      }
    };

    // reconnect socket if closes
    socket.onclose = e => {
      setTimeout(function() {
        this.connect();
      }.bind(this), 1000);
    };
  }

  setTotal(total) {
    this.total = total
  }

  setCurrent(current) {
    for (let id in current) {
      // show progressbar if being updated
      const container = document.getElementById(`env-progress-container${id}`);
      if (container.hasAttribute('hidden')) {
        container.removeAttribute('hidden');
        const btn = document.getElementById(`env-set-btn${id}`);
        if (btn) {
          btn.setAttribute('disabled', '');
        }
      }

      const env = current[id];
      const percent = ((env.current / env.total) || 0) * 100;
      const bar = document.getElementById(`env-progress${id}`);
      bar.style = `width: ${percent}%;`;
      bar.innerHTML = `${env.current}/${env.total}`;
      bar.setAttribute('aria-valuenow', percent);

      // Tell the user to refresh the page in case they are working on something.
      // I would just change all the buttons to set-x based on what happened, but that's
      // a lot of js that I'd rather let some js framework deal with in the future.
      if (percent === 100) {
        const message = document.getElementById(`env-progress-message${id}`);
        message.innerHTML = 'Environment visibility has changed. Please refresh the page for updated information.';
      }
    }
  }
}

window.onload = () => {
  new ManageEnvironments();
}
