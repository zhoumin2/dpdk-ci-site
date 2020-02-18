import { Component, h, render } from 'preact'

export default class Testrun extends Component {
  render() {
    return(
      {# Some objects may have a commit_id but don't have a branch. #}
      {(obj.branch &&
      <div>{ obj.branch.name }</div>
      )}
      <code>
        {# Some objects may not have a commit_url if they don't have a branch. #}
        {(obj.commit_url &&
          <a href="{{ obj.commit_url }}"> {{ obj.commit_id }} </a>
        ) || (
          <dive>{ obj.commit_id }</div>
        )}
      </code>
  }
}

