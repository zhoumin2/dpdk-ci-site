import { h, render } from 'preact'
import ResultSummary from './components/ResultSummary'
import { Row } from './row'

class TarballTable extends Row {
  constructor (props) {
    const table = document.getElementById('tarball-table')

    const linkStart = parseInt(table.dataset.start)
    const linkEnd = parseInt(table.dataset.end)
    const limit = parseInt(table.dataset.limit)
    const shown = table.dataset.shown
    const isAdmin = table.dataset.admin === 'True'

    super(props, 'tarballs', linkStart, linkEnd, limit, shown, isAdmin)
  }

  render () {
    return (
      <ul className="list-group mb-3">
        {this.state.rows.map(t =>
          <a href={t.detail_url} key={t.id} className="list-group-item list-group-item-action">
            {(t.branch &&
              <div>
                <div className="row">
                  <div className="col-sm">
                    <span className={`badge badge-${t.status_class}`} title={t.status_tooltip}>{t.status}</span>
                  </div>

                  <div className="col-sm text-sm-center">
                    Tarball {t.id}
                  </div>

                  <small className="col-sm text-sm-right">
                    <span className="text-muted" title="Repo/Branch tarball was created from">{t.branch.name}</span>
                  </small>
                </div>

                <div>
                  <small className="d-sm-flex justify-content-between mt-1">
                    <div><code title="Tarball created from commit">{t.commit_id}</code></div>

                    {(t.date &&
                      <div><span title="Tarball created date">{t.date}</span></div>
                    )}
                  </small>
                </div>
              </div>
            ) || (
              <div className="spinner-border spinner-border-sm text-secondary mt-3 mb-3" role="status">
                <span className="sr-only">Fetching tarball information...</span>
              </div>
            )}

            {t.status &&
              <div className="d-sm-flex justify-content-between">
                <ResultSummary obj={t}></ResultSummary>

                {(this.shown === 'all' || this.shown === 'with') && t.patchset &&
                  <a href={t.patchset.detail_url} title="Associated patch set">Patch set {t.patchset.id}</a>
                }
              </div>
            }
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

  render(<TarballTable />, domContainer)
}
