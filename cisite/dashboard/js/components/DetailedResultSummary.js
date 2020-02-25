import { Component, h } from 'preact'
import { errorPopup } from '../utils'

export default class DetailedResultSummary extends Component {
  constructor (props) {
    super(props)
    this.state = {
      testcases: {}
    }
  }

  componentDidMount () {
    fetch('?result_summary=true').then(res => {
      if (res.ok) {
        return res.json()
      }
    }).then(json => {
      this.setState(() => {
        return json
      })
    }).catch(errorPopup)
  }

  render () {
    return (
      <div>
        <h2>
          Test Results
          <small>
            <span className={`badge badge-${this.state.status_class} align-middle ml-1`} title={this.state.status_tooltip}>
              {this.state.status}
            </span>
          </small>
        </h2>

        {this.state.testcases &&
          <div className="mb-3 card">
            <div className="card-body">
              {(this.state.status && Object.values(this.state.testcases).map(tc =>
                <div title={`${tc.testcase.name}: ${tc.passed} passed, ${tc.failed} failed`} className="text-nowrap d-inline-block mr-4">
                  {(tc.testcase.description_url &&
                    <a href={tc.testcase.description_url}>{tc.testcase.name}</a>
                  ) || (
                    <span>{tc.testcase.name}</span>
                  )}
                  <br/>

                  <span>
                    {[...Array(tc.passed)].map((_, i) =>
                      <span key={i} className="text-success fas fa-check-circle mr-1"></span>
                    )}
                  </span>

                  <span>
                    {[...Array(tc.failed)].map((_, i) =>
                      <span key={i} className="text-danger fas fa-times-circle mr-1"></span>
                    )}
                  </span>
                </div>
              )) || (
                <span className="spinner-border spinner-border-sm text-secondary mr-1 my-2" role="status" title="Fetching results...">
                  <span className="sr-only">Fetching results...</span>
                </span>
              )}
            </div>
          </div>
        }
      </div>
    )
  }
}
