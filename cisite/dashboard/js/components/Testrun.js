import { Component, Fragment, h } from 'preact'
import Commit from './Commit'

export default class Testrun extends Component {
  render () {
    return (
      <div>
        <dl className="row">
          <dt className="col-sm-3 col-lg-2">Test run at</dt>
          <dd className="col-sm-9 col-lg-10">
            {new Date(this.props.r.timestamp).toLocaleString()}
            {(this.props.r.timedelta && this.props.isAdmin &&
              <div>
                ({this.props.r.timedelta} since patchset posted)
              </div>
            )}
          </dd>

          {this.props.r.commit_id &&
            <>
              <dt className="col-sm-3 col-lg-2">Baseline</dt>
              <dd className="col-sm-9 col-lg-10">
                <Commit obj={this.props.r}></Commit>
              </dd>
            </>
          }

          <dt className="col-sm-3 col-lg-2">Fail/Total</dt>
          <dd className="col-sm-9 col-lg-10">{this.props.r.failure_count}/{this.props.r.results.length}</dd>
        </dl>

        {(this.props.r.results &&
          <div className="table-responsive-sm">
            <table className="table table-hover table-sm mb-0">
              <thead>
                <tr>
                  <th>Result</th>
                  {this.props.r.results.length !== 0 && this.props.r.results[0].measurement &&
                    <>
                      {Object.values(this.props.r.results[0].measurement.parameters).map(parameter =>
                        <th>
                          {parameter.name} ({parameter.unit})
                        </th>
                      )}

                      {this.props.r.results[0].measurement &&
                        <th>
                          {this.props.r.results[0].measurement.name} Difference ({this.props.r.results[0].measurement.unit})
                        </th>
                      }
                    </>
                  }
                </tr>
              </thead>
              <tbody>
                {Object.values(this.props.r.results).map(item =>
                  <>
                    {((!this.props.environment.live_since || (new Date(this.props.environment.live_since) / 1000) > (new Date(this.props.r.timestamp) / 1000)) &&
                      <tr className="table-secondary" title="This run does not affect the overall result above.">
                        <td className={`text-${item.result_class}`}>{item.result}</td>

                        {item.measurement &&
                          <>
                            {Object.values(item.measurement.parameters).map(parameter =>
                              <td>{parameter.value}</td>
                            )}

                            {(item.difference !== null &&
                              <td>{+item.difference.toFixed(5)}</td>
                            ) || (
                              <td></td>
                            )}
                          </>
                        }
                      </tr>
                    ) || (
                      <tr className={`table-${item.result_class}`}>
                        <td>{item.result}</td>

                        {item.measurement &&
                          <>
                            {Object.values(item.measurement.parameters).map(parameter =>
                              <td>{parameter.value}</td>
                            )}

                            {(item.difference !== null &&
                              <td>{+item.difference.toFixed(5)}</td>
                            ) || (
                              <td></td>
                            )}
                          </>
                        }
                      </tr>
                    )}
                  </>
                )}
              </tbody>
            </table>
          </div>
        )}

        {this.props.r.log_upload_file &&
          <>
            <a className="btn btn-sm btn-info mt-3 mr-3" href={this.props.r.log_upload_file}>Download artifacts</a>
            {this.props.r.is_owner &&
              <form className="d-inline" action={`${this.props.r.togglepublic_url}?next=${window.location.pathname}`} method="POST">
                <input type="hidden" name="csrfmiddlewaretoken" value={this.props.csrf}/>
                {(this.props.r.public_download &&
                  <input type="submit" className="btn btn-sm btn-secondary mt-3 mr-3" value="Set download private"/>
                ) || (
                  <input type="submit" className="btn btn-sm btn-secondary mt-3 mr-3" value="Set download public"/>
                )}
              </form>
            }
          </>
        }

        {this.props.environment.pipeline && this.props.r.testcase.pipeline &&
          <form className="d-inline" action={`${this.props.r.rerun_url}?next=${window.location.pathname}`} method="POST">
            <input type="hidden" name="csrfmiddlewaretoken" value={this.props.csrf}/>
            <input type="submit" className="btn btn-sm btn-warning mt-3" value="Rerun"/>
          </form>
        }
      </div>
    )
  }
}
