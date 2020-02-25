import { Component, h } from 'preact'

export default class Testrun extends Component {
  render () {
    return (
      <span>
        {/* Some objects may have a commit_id but don't have a branch. */}
        {this.props.obj.branch &&
          <span className="mr-1">{this.props.obj.branch.name}</span>
        }
        (
        <code>
          {/* Some objects may not have a commit_url if they don't have a branch. */}
          {(this.props.obj.commit_url &&
            <a href={this.props.obj.commit_url}>{this.props.obj.commit_id}</a>
          ) || (
            <span>{this.props.obj.commit_id}</span>
          )}
        </code>
        )
      </span>
    )
  }
}
