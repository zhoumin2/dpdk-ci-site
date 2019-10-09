import { Component, h } from 'preact'

export default class ResultSummary extends Component {
  render () {
    return (
      <div>
        {this.props.obj.result_summary.incomplete > 0 &&
          <div title={`${this.props.obj.result_summary.incomplete} incomplete environments`} className="text-nowrap d-inline-block mr-4">
            {[...Array(this.props.obj.result_summary.incomplete)].map((_, i) =>
              <span key={i} className="text-secondary fas fa-circle mr-1"></span>
            )}
          </div>
        }

        {Object.values(this.props.obj.result_summary.testcases).map(tc =>
          <div key={tc.testcase.name} title={`${tc.testcase.name}: ${tc.passed} passed, ${tc.failed} failed`} className="text-nowrap d-inline-block mr-4">
            {/* If a child contains multiple loops, then the 'key' does not
                work properly, and results in duplicate elements. Thus the
                loops are wrapped with a span. */}
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
        )}
      </div>
    )
  }
}
