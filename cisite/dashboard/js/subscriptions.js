import { handleResponse, errorPopup } from './utils'

/**
 * Subscription manager for environments.
 */
export class SubscriptionManager {
  constructor() {
    const subscribeCheckboxes = document.getElementsByClassName('subscribe');

    // check if we are on the subscriptions page
    if (!subscribeCheckboxes) {
      return;
    }

    Array.from(subscribeCheckboxes).forEach(element => {
      // set 'this' to the subscriptionmanager instead of the element
      element.addEventListener('click', this.handleSubscriptionCheckbox.bind(this));
    });

    const sendMethods = document.getElementsByClassName('send-method');

    Array.from(sendMethods).forEach(element => {
      // set 'this' to the subscriptionmanager instead of the element
      element.addEventListener('change', this.handleSendChange.bind(this));
    });
  }

  /**
   * Handle the subscription checkbox clicked event.
   * @param {!Event} e
   */
  handleSubscriptionCheckbox(e) {
    // disable button until the request goes through
    e.target.disabled = true;

    const subscription = e.target.form.dataset.subscription;
    const environment = e.target.form.dataset.environment;
    const csrftoken = e.target.form.elements.csrfmiddlewaretoken.value;

    if (subscription === undefined) {
      this.add(csrftoken, e.target.form, e.target, environment);
    } else {
      this.remove(csrftoken, e.target.form, e.target, environment, subscription);
    }
  }

  /**
   * Add a subscription.
   * @param {!string} csrftoken
   * @param {!HTMLFormsControlCollection} form
   * @param {!HTMLInputElement} target
   * @param {!number} environment
   */
  add(csrftoken, form, target, environment) {
    const request = new Request('./', {
      credentials: 'same-origin',
      headers: {'X-CSRFToken': csrftoken, 'Content-Type': 'application/json; charset=utf-8'},
      method: 'POST',
      body: JSON.stringify({'environment': form.dataset.url, 'email_success': this.getSendValue(form), 'how': 'to'})
    });

    fetch(request).then(response => {
      if (handleResponse(response)) {
        response.json().then(json => {
          form.dataset.subscription = json.id;
          document.getElementById('send-' + environment).disabled = false;
          target.disabled = false;
        });
      }
    }).catch(errorPopup);
  }

  /**
   * Remove a subscription.
   * @param {!string} csrftoken
   * @param {!HTMLFormsControlCollection} form
   * @param {!HTMLInputElement} target
   * @param {!number} environment
   * @param {!number} subscription
   */
  remove(csrftoken, form, target, environment, subscription) {
    const request = new Request('./' + subscription + '/', {
      credentials: 'same-origin',
      headers: {'X-CSRFToken': csrftoken},
      method: 'DELETE'
    });

    fetch(request).then(response => {
      if (handleResponse(response)) {
        delete form.dataset.subscription;
        document.getElementById('send-' + environment).disabled = true;
        target.disabled = false;
      }
    }).catch(errorPopup);
  }

  /**
   * Parse the value from a string to boolean/null.
   * @param {!HTMLFormsControlCollection} form
   * @return {?boolean}
   */
  getSendValue(form) {
    const value = form.elements.send.value;
    if (value === 'true') {
      return true;
    } else if (value === 'false') {
      return false;
    }
    return null;
  }

  /**
   * Handle the select method box changed event.
   * @param {!Event} e
   */
  handleSendChange(e) {
    const subscription = e.target.form.dataset.subscription;
    const csrftoken = e.target.form.elements.csrfmiddlewaretoken.value;

    if (subscription !== undefined) {
      const request = new Request('./' + subscription + '/', {
        credentials: 'same-origin',
        headers: {'X-CSRFToken': csrftoken, 'Content-Type': 'application/json; charset=utf-8'},
        method: 'PATCH',
        body: JSON.stringify({'email_success': this.getSendValue(e.target.form)})
      });

      fetch(request).then(handleResponse).catch(errorPopup);
    }
  }
}
