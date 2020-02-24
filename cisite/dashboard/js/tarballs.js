import { h, render, Component } from 'preact'
import ResultSummary from './components/ResultSummary'
import { withRowSupport } from './row'

class TarballTable extends Component {
  render () {
    return (
      <ul className="list-group mb-3">
        {this.props.rows.map(t =>
          <a href={t.detail_url} key={t.js_id} className="list-group-item list-group-item-action">
            <div>
              <div className="row">
                <div className="col-sm">
                  {(t.result_summary && t.result_summary.status &&
                    <span className={`badge badge-${t.result_summary.status_class}`} title={t.result_summary.status_tooltip}>
                      {t.result_summary.status}
                    </span>
                  ) || (
                    <div className="spinner-border spinner-border-sm text-secondary" role="status" title="Fetching status...">
                      <span className="sr-only">Fetching status...</span>
                    </div>
                  )}
                </div>

                {/* Avoid changing font color as detail_url gets populated */}
                {t.id &&
                  <div className="col-sm text-sm-right text-md-center">
                    Tarball {t.id}
                  </div>
                }

                {t.date &&
                  <div className="col-md text-md-right">
                    <small title="Tarball created date">
                      {t.date}
                    </small>
                  </div>
                }
              </div>

              <div>
                <small className="d-sm-flex justify-content-between my-1">
                  <div><code title="Tarball created from commit">{t.commit_id}</code></div>

                  {(t.branch &&
                    <span className="text-muted" title="Repo/Branch tarball was created from">
                      {t.branch.name}
                    </span>
                  ) || (
                    <div class="d-inline-block">
                      {/* Avoid changing height of row when tarball gets populated */}
                      &nbsp;
                    </div>
                  )}
                </small>
              </div>

              <div className="d-sm-flex justify-content-between">
                {(typeof t.result_summary === 'object' &&
                  <ResultSummary obj={t}></ResultSummary>
                )}

                {/* Avoid changing height of row when results gets populated - or if results don't exist */}
                <div class="d-inline-block">
                  &nbsp;
                </div>

                {t.patchset &&
                  <a href={t.patchset.detail_url} title="Associated patch set">Patch set {t.patchset.id}</a>
                }
              </div>
            </div>
          </a>
        )}
      </ul>
    )
  }
}

export function initTarballs () {
  const domContainer = document.getElementById('tarball-table')

  // check if we are on the right page
  if (!domContainer) {
    return
  }

  const TarballTableWithRows = withRowSupport(
    TarballTable,
    'tarballs',
    parseInt(domContainer.dataset.start),
    parseInt(domContainer.dataset.end),
    domContainer.dataset.shown,
    domContainer.dataset.admin === 'True'
  )

  render(<TarballTableWithRows />, domContainer)
}
