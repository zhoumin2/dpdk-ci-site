import { h, render, Component } from 'preact'
import ResultSummary from './components/ResultSummary'
import { withRowSupport } from './row'

class DashboardTable extends Component {
  render () {
    return (
      <ul className="list-group mb-3">
        {this.props.rows.map(ps =>
          <a href={ps.detail_url} key={ps.js_id} className="list-group-item list-group-item-action">
            {(ps.error &&
              <div>{ps.error}</div>
            ) || (
              <div>
                <div className="row">
                  <div className="col-sm-6 col-md-4">
                    {(ps.result_summary && ps.result_summary.status &&
                      <span className={`badge badge-${ps.result_summary.status_class}`} title={ps.result_summary.status_tooltip}>
                        {ps.result_summary.status}
                      </span>
                    ) || (
                      <div className="spinner-border spinner-border-sm text-secondary" role="status" title="Fetching status...">
                        <span className="sr-only">Fetching status...</span>
                      </div>
                    )}
                  </div>

                  {ps.series &&
                    <div className="col-sm-6 text-sm-right col-md-4 text-md-center">
                      Patch {ps.series.patchwork_range_str}
                      {(ps.series.version > 1 &&
                        <span className="badge badge-pill badge-secondary ml-1" title="Patch version">v{ps.series.version}</span>
                      )}
                    </div>
                  }

                  {ps.series &&
                    <div className="col text-md-right">
                      <small title="Date submitted">{ps.series.date}</small>
                    </div>
                  }
                </div>

                {(ps.series &&
                  <div className="d-sm-flex justify-content-between my-1">
                    {ps.series.name}
                    <div className="text-sm-right text-muted">
                      <small>{ps.series.submitter}</small>
                    </div>
                  </div>
                ) || (
                  <div className="d-sm-flex justify-content-between mt-1 mb-1">
                    {/* Avoid changing height of row when series gets populated */}
                    &nbsp;
                  </div>
                )}

                <div className="d-sm-flex justify-content-between">
                  {(typeof ps.result_summary === 'object' &&
                    <ResultSummary obj={ps}></ResultSummary>
                  )}

                  {/* Avoid changing height of row when results gets populated - or if results don't exist */}
                  <div class="d-inline-block">
                    &nbsp;
                  </div>

                  {this.props.isAdmin &&
                    <small className="text-nowrap text-muted" title="The time it took from when the patchset was submitted to when the last test run completed.">
                      {(ps.time_to_last_test &&
                        ps.time_to_last_test
                      )}
                    </small>
                  }
                </div>
              </div>
            )}
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

  const DashboardTableWithRows = withRowSupport(
    DashboardTable,
    'patchsets',
    parseInt(domContainer.dataset.start),
    parseInt(domContainer.dataset.end),
    domContainer.dataset.shown,
    domContainer.dataset.admin === 'True'
  )

  render(<DashboardTableWithRows />, domContainer)
}
