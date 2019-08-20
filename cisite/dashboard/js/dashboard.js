import { h, render } from 'preact'
import ResultSummary from './components/ResultSummary'
import { Row } from './row'

class DashboardTable extends Row {
  constructor (props) {
    const table = document.getElementById('dashboard-table')

    const linkStart = parseInt(table.dataset.start)
    const linkEnd = parseInt(table.dataset.end)
    const limit = parseInt(table.dataset.limit)
    const shown = table.dataset.shown
    const isAdmin = table.dataset.admin === 'True'

    super(props, 'patchsets', linkStart, linkEnd, limit, shown, isAdmin)
  }

  render () {
    return (
      <table className="table table-hover">
        <thead>
          <tr>
            <th title="Patch status. More information can be found by hovering over a status or by seeing the about page.">Status</th>
            <th title="Patch information">Patch</th>
            {(this.isAdmin &&
              <th title="The time it took from when the patchset was submitted to when the last test run completed.">Time</th>
            )}
          </tr>
        </thead>

        <tbody>
          {this.state.rows.map(ps =>
            <tr key={ps.id}>
              <td>
                {(ps.status &&
                  <div>
                    <span className={`badge badge-${ps.status_class}`} title={ps.status_tooltip}>{ps.status}</span>

                    <ResultSummary obj={ps}></ResultSummary>
                  </div>
                ) || (
                  <div className="spinner-border spinner-border-sm text-secondary" role="status">
                    <span className="sr-only">Fetching patch information...</span>
                  </div>
                )}
              </td>

              <td>
                {(ps.series &&
                  <div>
                    <div className="d-flex justify-content-between flex-column flex-md-row">
                      <div>
                        <a href={ps.detail_url}>{ps.patchwork_range_str}</a>
                        {(ps.series.version > 1 &&
                          <span className="badge badge-pill badge-secondary" title="Patch version">v{ps.series.version}</span>
                        )}
                      </div>

                      <div className="text-muted">
                        <small>{ps.series.submitter}</small>
                      </div>
                    </div>

                    <div>
                      {ps.series.name}
                    </div>
                  </div>
                ) || (ps.error &&
                  <div>{ps.error}</div>
                ) || (
                  <div>
                    <br/>
                    <br/>
                  </div>
                )}
              </td>

              {this.isAdmin &&
                <td className="text-nowrap">
                  {(ps.time_to_last_test &&
                    ps.time_to_last_test
                  )}
                </td>
              }
            </tr>
          )}
        </tbody>
      </table>
    )
  }
}

export function initDashboard () {
  const domContainer = document.getElementById('dashboard-table')

  // check if we are on the right page
  if (!domContainer) {
    return
  }

  render(<DashboardTable />, domContainer)
}
