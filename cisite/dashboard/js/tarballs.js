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
      <table className="table table-hover">
        <thead>
          <tr>
            <th title="Tarball result. More information can be found by hovering over a status or by seeing the about page.">Status</th>
            {(this.shown === 'all' || this.shown === 'with') &&
              <th className="text-nowrap" title="Associated patch set">Patch set</th>
            }
            <th title="Tarball created from commit">Tarball</th>
            <th title="Tarball created date">Date</th>
          </tr>
        </thead>

        <tbody>
          {this.state.rows.map(t =>
            <tr key={t.id}>
              <td>
                {(t.status &&
                  <div>
                    <span className={`badge badge-${t.status_class}`} title={t.status_tooltip}>{t.status}</span>

                    <ResultSummary obj={t}></ResultSummary>
                  </div>
                ) || (
                  <div className="spinner-border spinner-border-sm text-secondary" role="status">
                    <span className="sr-only">Fetching tarball information...</span>
                  </div>
                )}
              </td>

              {(this.shown === 'all' || this.shown === 'with') &&
                <td>
                  {(t.patchset &&
                    <a href={t.patchset.detail_url}>{t.patchset.id}</a>
                  )}
                </td>
              }

              <td className="text-truncate">
                {(t.branch &&
                  <div>
                    <div className="d-flex justify-content-between">
                      <a href={t.detail_url}>{t.id}</a>
                      <small><span className="text-muted" title="Repo/Branch tarball was created from">{t.branch.name}</span></small>
                    </div>

                    <div>
                      <small><code>{t.commit_id}</code></small>
                    </div>
                  </div>
                ) || (
                  <div>
                    <br/>
                    <br/>
                  </div>
                )}
              </td>

              <td className="text-nowrap">
                {(t.date &&
                  t.date
                )}
              </td>
            </tr>
          )}
        </tbody>
      </table>
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
