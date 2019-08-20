import { Component, h, render } from 'preact'
import { handleResponse, errorPopup } from './utils'

export class Subscriptions extends Component {
  constructor (props) {
    super(props)

    this.state = {
      env_sub_pairs: []
    }
  }

  componentDidMount () {
    fetch('?json').then(res => {
      if (res.ok) {
        return res.json()
      }
    }).then(json => {
      this.setState(state => {
        // json also contains csrf token, etc
        state = json
        state.env_sub_pairs = json.env_sub_pairs.map(envSub => {
          if (envSub.subscription) {
            // convert to string for use in form
            envSub.subscription.email_success = String(envSub.subscription.email_success)
          }
          // used to disable the checkbox while updating the subscription
          envSub.updating = false
          return envSub
        })
        return state
      })
    })
  }

  handleSubscriptionCheckbox (e, index) {
    // disable button until the request goes through
    this.setState(state => {
      state.env_sub_pairs[index].updating = true
      return state
    })

    const envSub = this.state.env_sub_pairs[index]
    const subscription = envSub.subscription

    if (subscription === null) {
      this.add(index, e.target.form, envSub.environment.url)
    } else {
      this.remove(index, subscription.id)
    }
  }

  getSendValue (value) {
    if (value === 'true') {
      return true
    } else if (value === 'false') {
      return false
    }
    return null
  }

  add (index, form, url) {
    const request = new Request('./', {
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': this.state.csrftoken, 'Content-Type': 'application/json; charset=utf-8' },
      method: 'POST',
      body: JSON.stringify({
        environment: url,
        email_success: this.getSendValue(form.elements.send.value),
        how: 'to'
      })
    })

    fetch(request).then(response => {
      if (handleResponse(response)) {
        response.json().then(json => {
          this.setState(state => {
            state.env_sub_pairs[index].subscription = {
              id: json.id, email_success: 'null'
            }
            state.env_sub_pairs[index].updating = false
            return state
          })
        })
      }
    }).catch(errorPopup)
  }

  remove (index, subscription) {
    const request = new Request('./' + subscription + '/', {
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': this.state.csrftoken },
      method: 'DELETE'
    })

    fetch(request).then(response => {
      if (handleResponse(response)) {
        this.setState(state => {
          state.env_sub_pairs[index].subscription = null
          state.env_sub_pairs[index].updating = false
          return state
        })
      }
    }).catch(errorPopup)
  }

  handleSendChange (e, index) {
    const envSub = this.state.env_sub_pairs[index]
    const subscription = envSub.subscription
    const value = e.target.form.elements.send.value

    if (subscription !== null) {
      const request = new Request('./' + subscription.id + '/', {
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': this.state.csrftoken, 'Content-Type': 'application/json; charset=utf-8' },
        method: 'PATCH',
        body: JSON.stringify({ email_success: this.getSendValue(value) })
      })

      this.setState(state => {
        state.env_sub_pairs[index].subscription.email_success = value
        return state
      })

      fetch(request).then(handleResponse).catch(errorPopup)
    }
  }

  render () {
    return (
      <ul className="list-group list-group-flush">
        {this.state.env_sub_pairs.map((envSub, index) =>
          <li className="list-group-item" key={envSub.environment.id}>
            <h5 className="card-title">{envSub.environment.name}</h5>

            <form autoComplete="off">
              <div className="form-row">
                <div className="col-sm-4">
                  <div className="form-check col-form-label">
                    <input
                      type="checkbox"
                      className="form-check-input subscribe"
                      id={`env-sub-${envSub.environment.id}`}
                      checked={envSub.subscription !== null}
                      disabled={envSub.updating}
                      onChange={e => this.handleSubscriptionCheckbox(e, index)}
                    />
                    <label className="form-check-label" htmlFor={`env-sub-${envSub.environment.id}`}>Subscribe</label>
                  </div>
                </div>

                <div className="col-sm-4 text-sm-right">
                  <label className="col-form-label">Send method</label>
                </div>

                <div className="col-sm-4">
                  <select
                    className="form-control send-method"
                    name="send"
                    value={envSub.subscription === null ? 'null' : envSub.subscription.email_success}
                    disabled={!envSub.subscription}
                    onChange={e => this.handleSendChange(e, index)}
                  >
                    <option value="null">Inherit (On failure)</option>
                    <option value="false">On failure</option>
                    <option value="true">Always</option>
                  </select>
                </div>
              </div>
            </form>
          </li>
        )}
      </ul>
    )
  }
}

export function initSubscriptionManager () {
  const domContainer = document.getElementById('subscription-manager')

  // check if we are on the right page
  if (!domContainer) {
    return
  }

  render(<Subscriptions />, domContainer)
}
