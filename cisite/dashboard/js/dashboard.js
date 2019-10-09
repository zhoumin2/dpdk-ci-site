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
      <ul className="list-group mb-3">
        {this.state.rows.map(ps =>
          <a href={ps.detail_url} key={ps.id} className="list-group-item list-group-item-action">
            {(ps.series &&
              <div>
                <div className="row">
                  {ps.status &&
                    <div className="col-sm-6 col-md-4">
                      <span className={`badge badge-${ps.status_class}`} title={ps.status_tooltip}>{ps.status}</span>
                    </div>
                  }

                  <div className="col-sm-6 text-sm-right col-md-4 text-md-center">
                    Patch {ps.patchwork_range_str}
                    {(ps.series.version > 1 &&
                      <span className="badge badge-pill badge-secondary ml-1" title="Patch version">v{ps.series.version}</span>
                    )}
                  </div>
                </div>

                <div className="d-sm-flex justify-content-between mt-1 mb-1">
                  {ps.series.name}
                  <div className="text-sm-right text-muted">
                    <small>{ps.series.submitter}</small>
                  </div>
                </div>
              </div>
            ) || (ps.error &&
              <div>{ps.error}</div>
            ) || (
              <div className="spinner-border spinner-border-sm text-secondary mt-3 mb-3" role="status">
                <span className="sr-only">Fetching tarball information...</span>
              </div>
            )}

            <div className="d-sm-flex justify-content-between">
              {(ps.status &&
                <ResultSummary obj={ps}></ResultSummary>
              )}

              {this.isAdmin &&
                <small className="text-nowrap text-muted" title="The time it took from when the patchset was submitted to when the last test run completed.">
                  {(ps.time_to_last_test &&
                    ps.time_to_last_test
                  )}
                </small>
              }
            </div>
          </a>
        )}
      </ul>
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
