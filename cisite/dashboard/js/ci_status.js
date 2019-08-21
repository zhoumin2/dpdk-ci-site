import { Component, h, render } from 'preact'

export class CIStatus extends Component {
  constructor (props) {
    super(props)

    this.state = {
      jobs: []
    }
  }

  componentDidMount () {
    const cistatus = document.getElementById('ci-status')
    const jobs = cistatus.dataset.jobsurl
    fetch(jobs).then(res => {
      if (res.ok) {
        return res.json()
      }
    }).then(json => {
      this.setState(state => {
        state.jobs = json
        return state
      }, () => {
        this.updateJobs(json)
      })
    })
  }

  updateJobs (jobs) {
    jobs.forEach((job, index) => {
      fetch(job.url).then(res => {
        if (res.ok) {
          return res.json()
        }
      }).then(json => {
        this.setState(state => {
          state.jobs[index] = json
          return state
        })
      })
    })
  }

  render () {
    return (
      <div className="table-responsive">
        <table className="table table-sm">
          <thead>
            <tr>
              <th scope="col">Status</th>
              <th scope="col">Job</th>
              <th scope="col">Typical Run Time</th>
            </tr>
          </thead>
          <tbody>
            {this.state.jobs.map(job =>
              <tr key={job.name}>
                <td>{job.status}</td>
                <td>
                  <div class="text-nowrap">{job.name}</div>
                  <div className="text-muted">{job.description}</div>
                </td>
                <td class="text-nowrap">
                  {(job.estimatedDuration &&
                    <div>{job.estimatedDuration}</div>
                  ) || (
                    <div className="spinner-border spinner-border-sm text-secondary" role="status">
                      <span className="sr-only">Fetching...</span>
                    </div>
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    )
  }
}

export function initCIStatus () {
  const domContainer = document.getElementById('ci-status')

  // check if we are on the right page
  if (!domContainer) {
    return
  }

  render(<CIStatus />, domContainer)
}
