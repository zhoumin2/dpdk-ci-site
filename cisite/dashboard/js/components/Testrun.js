import { Component, h, render } from 'preact'

export default class Testrun extends Component {
  render() {
    return(
    <div>
      <dl class="row">
        <dt class="col-sm-3 col-lg-2">Test run at</dt>
        <dd class="col-sm-9 col-lg-10">
          {this.props.r.timestamp}
          {(this.props.r.timedelta && request.user.is_superuser &&
          <div>
            ({this.props.r.timedelta} since patchset posted)
            </div>
          )}
        </dd>

        {(r.commit_id &&
        <div>
          <dt class="col-sm-3 col-lg-2">Baseline</dt>
          <dd class="col-sm-9 col-lg-10">
             <Commit r={this.props.r}></Commit>
          </dd>
         </div>
        )}

        <dt class="col-sm-3 col-lg-2">Fail/Total</dt>
        <dd class="col-sm-9 col-lg-10">{ this.props.r.failure_count }/{ this.props.r.results|length }</dd>
      </dl>

      {(this.props.r.results &&
        <div class="table-responsive-sm">
          <table class="table table-hover table-sm mb-0">
            <thead>
              <tr>
                <th>Result</th>
                {Object.values(this.props.r.results[0].measurement.parameters.values).map(parameter =>
                  <th>
                    { parameter.name }
                    ({ parameter.unit })
                  </th>
                )}

                {(this.props.r.results[0].measurement &&
                  <th>
                    { this.props.r.results[0].measurement.name } Difference
                    ({ this.props.r.results[0].measurement.unit })
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {Object.values(this.props.r.results).map(item =>
                {((!environment.live_since || environment.live_since > this.props.r.timestamp) &&
                  <tr class="table-secondary" title="This run does not affect the overall result above.">
                    <td class={`text-${item.result_class}`}>{ item.result }</td>
                  {Object.values(item.measurement.parameters.values).map(parameter =>
                    <td>{ parameter.value }</td>
                  )}

                  {(!item.difference &&
                    <td>{ item.difference }</td>
                  )}
                </tr>
                ) || (
                  <tr class={`table-${item.result_class}`}>
                    <td>{ item.result }</td>
                  {Object.values(item.measurement.parameters.values).map(parameter =>
                    <td>{ parameter.value }</td>
                  )}

                  {(!item.difference &&
                    <td>{ item.difference }</td>
                  )}
                </tr>
                )}
              )}
            </tbody>
          </table>
        </div>
      )}

      {(this.props.r.log_upload_file &&
      <div>
        <a class="btn btn-sm btn-info mt-3 mr-3" href="{{ r.log_upload_file }}">Download artifacts</a>
        {(this.props.r.is_owner &&
          <form class="d-inline" action="{% url 'testrun_togglepublic' r.id %}?next={{ request.path }}" method="POST">
            <input type="hidden" name="csrfmiddlewaretoken" value={this.props.csrf}/>
            {(this.props.r.public_download &&
              <input type="submit" class="btn btn-sm btn-secondary mt-3 mr-3" value="Set download private"/>
            ) || (
              <input type="submit" class="btn btn-sm btn-secondary mt-3 mr-3" value="Set download public"/>
            )}
          </form>
        )}
      </div>
      )}

      {(environment.pipeline && this.props.r.testcase.pipeline &&
        <form class="d-inline" action="{% url 'dashboard_rerun' r.id %}?next={{ request.path }}" method="POST">
            <input type="hidden" name="csrfmiddlewaretoken" value={this.props.csrf}/>
          <input type="submit" class="btn btn-sm btn-warning mt-3" value="Rerun"/>
        </form>
      )}
      </div>
    )
  }
}

