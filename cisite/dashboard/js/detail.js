import Testrun from './components/Testrun'
import DetailedResultSummary from './components/DetailedResultSummary'
import { Component, Fragment, h, render } from 'preact'
import { errorPopup } from './utils'

export class EnvironmentResults extends Component {
  constructor (props) {
    super(props)
    const environmentResults = document.getElementById('environment-results')
    this.env_id_list = environmentResults.dataset.environments
    this.env_name_list = environmentResults.dataset.environmentnames
    this.state = {
      environments: {},
      testcases: {},
      tarball: {}
    }
  }

  componentDidMount () {
    if (this.env_id_list === '') {
      return
    }

    fetch('?environments=' + this.env_id_list).then(res => {
      if (res.ok) {
        return res.json()
      }
    }).then(json => {
      this.setState(() => {
        return json
      })
    }).catch(errorPopup)
  }

  componentDidUpdate () {
    // this update should only happen once
    this.props.expandManager.init()
  }

  render () {
    return (
      <div>
        {(Object.keys(this.state.environments).length !== 0 && Object.values(this.state.environments).map(environment =>
          <div className="card mb-3" id={`accordion-${environment.id}`}>
            <button className="card-header d-flex justify-content-between align-items-center btn text-left" data-toggle="collapse" data-target={`#collapse-${environment.id}`} aria-expanded="false" aria-controls={`collapse-${environment.id}`}>
              <h3 className="mb-0 env-title">{environment.name}</h3>
              <div className="text-nowrap">
                {!environment.public &&
                  <span className="text-secondary fas fa-eye-slash mr-1" title="The environment is private"></span>
                }

                {!environment.live_since &&
                  <span className="text-secondary fas fa-minus-circle mr-1" title="This run does not affect the overall result above."></span>
                }

                {(environment.all_pass &&
                  <span className="text-success fas fa-check-circle" title="All test cases passed"></span>
                ) || (environment.all_pass === false &&
                  <span className="text-danger fas fa-times-circle" title="At least one test case did not pass"></span>
                ) || (
                  <span className="text-secondary fas fa-circle" title="There are not yet any runs for this patch set"></span>
                )}
              </div>
            </button>
            <div id={`collapse-${environment.id}`} className="collapse collapsible" aria-labelledby={`env-${environment.id}`} data-parent={`#accordion-${environment.id}`} data-all-pass={environment.all_pass}>
              <div className="card-body">
                {(environment.hardware_description &&
                  <h4><a href={environment.hardware_description}>Configuration Information</a></h4>
                ) || (
                  <h4>Configuration Information</h4>
                )}

                <dl className="row">
                  <dt className="col-sm-3 col-lg-2">Kernel</dt>
                  <dd className="col-sm-9 col-lg-10">{environment.kernel_name} {environment.kernel_version}</dd>

                  <dt className="col-sm-3 col-lg-2">Compiler</dt>
                  <dd className="col-sm-9 col-lg-10">{environment.compiler_name} {environment.compiler_version}</dd>
                </dl>

                {this.state.isAdmin && environment.pipeline && this.state.tarball &&
                  <form className="form-inline" action={`${this.state.tarball.build_url}/?next=${window.location.pathname}`} method="POST">
                    <input type="hidden" name="csrfmiddlewaretoken" value={this.state.csrf}/>
                    <label className="mr-2" for="pipeline-select" title="Used for initially running a test in case it could not be ran automatically">Run pipeline</label>
                    <select id="pipeline-select" className="form-control form-control-sm mr-2 mb-2 mb-sm-0" name="pipeline">
                      {Object.values(this.state.testcases).map(testcase =>
                        <>
                          {testcase.pipeline &&
                            <option value={`${testcase.pipeline}-${environment.pipeline}`}>{testcase.name}</option>
                          }
                        </>
                      )}
                    </select>
                    <input type="submit" className="btn btn-sm btn-warning" value="Build"/>
                  </form>
                }

                {Object.keys(environment.testcases).length !== 0 && Object.values(environment.testcases).map(tc =>
                  <>
                    {(Object.keys(tc.runs).length > 1 &&
                      <div className="card mt-3">
                        <div className="card-header">
                          <div className="d-flex flex-column justify-content-lg-between flex-lg-row">
                            <h4 className="mb-lg-0 mr-lg-2">
                              {(tc.description_url &&
                                <a href={tc.description_url}>{tc.name}</a>
                              ) || (
                                <div>{tc.name}</div>
                              )}
                            </h4>
                            <ul className="nav nav-tabs card-header-tabs">
                              {tc.runs.map((r, i) =>
                                <li className="nav-item">
                                  <a className={`nav-link ${i === 0 ? 'active' : ''}`} data-toggle="tab" href={`#run-${r.id}`} role="tab" aria-controls={`run-${r.id}`} aria-selected={i === 0 ? 'true' : 'false'}>
                                    Run {Object.keys(environment.testcases).length - i + 1}
                                  </a>
                                </li>
                              )}
                            </ul>
                          </div>
                        </div>
                        <div className="card-body">
                          <div className="tab-content">
                            {tc.runs.map((r, i) =>
                              <div className={`tab-pane fade ${i === 0 ? 'show active' : ''}`} id={`run-${r.id}`} role="tabpanel" aria-labelledby={`run-${r.id}-tab`}>
                                <Testrun r={r} isAdmin={this.state.isAdmin} environment={environment} csrf={this.state.csrf}></Testrun>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ) || (Object.keys(tc.runs).length === 1 &&
                      <div className="card mt-3">
                        <h4 className="card-header">
                          {(tc.description_url &&
                            <a href={tc.description_url}>{tc.name}</a>
                          ) || (
                            <div>{tc.name}</div>
                          )}
                        </h4>
                        <div className="card-body">
                          <Testrun r={tc.runs[0]} isAdmin={this.state.isAdmin} environment={environment} csrf={this.state.csrf}></Testrun>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )) || (this.env_name_list && this.env_name_list.split(',').map(name =>
          <div className="card mb-3">
            <div className="card-header d-flex justify-content-between align-items-center">
              <h3 className="mb-0">{name}</h3>
              <span className="spinner-border spinner-border-sm text-secondary mr-1" role="status" title="Fetching results...">
                <span className="sr-only">Fetching results...</span>
              </span>
            </div>
          </div>
        )) || (
          <p>
            There are not yet any runs for this patch set or you do not have
            permission to view detailed results for any test runs for this patch
            set.
          </p>
        )}
      </div>
    )
  }
}

// All + "Everything else" = radio
// "Everything else" = checkbox
// "Custom" checkbox: allows users to always expand specific environments.
// Since that can include pass/fail/incomplete, then special checks are
// in place to make sure collapsing custom selected environments doesn't
// also collapse pass/fail/incomplete and vice-versa.
class Expander {
  constructor () {
    this.canDisable = true
  }

  hideIfAll () {
    const inverseSelector = this.inverseSelector
    const expandAllClassList = document.getElementById('expand-all').classList
    if (expandAllClassList.contains('active')) {
      if (inverseSelector) {
        $(inverseSelector).collapse('hide')
      }
      expandAllClassList.remove('active')
      localStorage.setItem('expand-all', false)
      document.getElementById('expand-all-icon').classList.remove('fa-dot-circle')
      document.getElementById('expand-all-icon').classList.add('fa-circle')
    }
  }

  checkboxSelect (selected) {
    localStorage.setItem(this.setting, selected)
    if (selected) {
      this.button.classList.add('active')
      this.icon.classList.remove('fa-square')
      this.icon.classList.add('fa-check-square')
    } else {
      this.button.classList.remove('active')
      this.icon.classList.remove('fa-check-square')
      this.icon.classList.add('fa-square')
    }
  }

  collapse (selected, collapse) {
    if (selected) {
      this.hideIfAll()
      $(this.selector).collapse('show')
    } else {
      if (collapse) {
        $(this.collapseSelector).collapse('hide')
      }
    }
  }

  checkboxSelectCollapse (selected, collapse) {
    this.checkboxSelect(selected)
    this.collapse(selected, collapse)
  }

  get collapseSelector () {
    if (!JSON.parse(localStorage.getItem('expand-custom'))) {
      return this.selector
    }

    const expandCustomList = JSON.parse(localStorage.getItem('expand-custom-list'))
    if (!expandCustomList) {
      return this.selector
    }

    // get all ids
    let ids = []
    const collapses = document.querySelectorAll(this.selector)
    collapses.forEach(collapse => ids.push('#' + collapse.id))

    // remove expandCustomList from ids, then turn into selector
    ids = ids.filter(id => !expandCustomList.includes(id)).join(',')

    return ids !== '' ? ids : null
  }

  init () {
    // check saved preferences
    if (JSON.parse(localStorage.getItem(this.setting))) {
      this.checkboxSelectCollapse(true)
    }

    if (this.canDisable) {
      // use disabled class instead of attribute to allow user to save/update preference
      if (document.querySelectorAll(this.selector).length === 0) {
        this.button.classList.add('disabled')
      }
    }

    // create event handlers
    this.button.addEventListener('click', e => {
      if (e.currentTarget.classList.contains('active')) {
        this.checkboxSelectCollapse(false, true)
      } else {
        this.checkboxSelectCollapse(true)
      }
    })
  }
}

class ExpandPass extends Expander {
  constructor () {
    super()
    this.button = document.getElementById('expand-pass')
    this.icon = document.getElementById('expand-pass-icon')
    this.setting = 'expand-pass'
    this.selector = '.collapsible[data-all-pass="true"]'
    this.inverseSelector = '.collapsible:not([data-all-pass="true"])'
  }
}

class ExpandFail extends Expander {
  constructor () {
    super()
    this.button = document.getElementById('expand-fail')
    this.icon = document.getElementById('expand-fail-icon')
    this.setting = 'expand-fail'
    this.selector = '.collapsible[data-all-pass="false"]'
    this.inverseSelector = '.collapsible:not([data-all-pass="false"])'
  }
}

class ExpandIncomplete extends Expander {
  constructor () {
    super()
    this.button = document.getElementById('expand-incomplete')
    this.icon = document.getElementById('expand-incomplete-icon')
    this.setting = 'expand-incomplete'
    this.selector = '.collapsible[data-all-pass=""]'
    this.inverseSelector = '.collapsible:not([data-all-pass=""])'
  }
}

class ExpandCustom extends Expander {
  constructor () {
    super()
    this.button = document.getElementById('expand-custom')
    this.icon = document.getElementById('expand-custom-icon')
    this.setting = 'expand-custom'
    this.canDisable = false

    this.customConflictSettings = ['expand-pass', 'expand-fail', 'expand-incomplete']
    this.customConflictSelectors = ['true', 'false', '']
  }

  get selector () {
    const expandCustomList = JSON.parse(localStorage.getItem('expand-custom-list'))
    if (expandCustomList) {
      return expandCustomList.join(',')
    }
  }

  get collapseSelector () {
    let expandCustomList = JSON.parse(localStorage.getItem('expand-custom-list'))
    if (!expandCustomList) {
      return
    }

    // only collapse custom selected, not pass/fail/incomplete if they are expanded
    const ids = []
    for (const i in this.customConflictSettings) {
      // get ids from expanded
      if (JSON.parse(localStorage.getItem(this.customConflictSettings[i]))) {
        const collapses = document.querySelectorAll('.collapsible[data-all-pass="' + this.customConflictSelectors[i] + '"]')
        collapses.forEach(collapse => ids.push('#' + collapse.id))
      }
    }

    // remove selected ids from saved ids
    expandCustomList = expandCustomList.filter(id => !ids.includes(id))

    return expandCustomList.join(',')
  }

  get inverseSelector () {
    const selector = this.selector
    if (selector) {
      return '.collapsible:not(' + selector + ')'
    }
  }

  init () {
    super.init()

    // if the card header is clicked, then add to expand-custom-list
    document.querySelectorAll('[data-toggle="collapse"]').forEach(elem => {
      elem.addEventListener('click', e => {
        // don't bubble events if clicking on a link within header
        if (e.target.tagName === 'A') {
          e.stopPropagation()
          return
        }

        let expandCustomSetting = JSON.parse(localStorage.getItem('expand-custom-list'))
        if (!expandCustomSetting) {
          expandCustomSetting = []
        }

        const env = e.currentTarget.dataset.target
        // hopefully this isn't a race condition? (since it's hiding at the same time)
        // if it has 'show', that means it's transitioning to be collapsed
        if (document.querySelector(env).classList.contains('show')) {
          expandCustomSetting = expandCustomSetting.filter(e => e !== env)
        } else {
          expandCustomSetting.push(env)
        }

        localStorage.setItem('expand-custom-list', JSON.stringify(expandCustomSetting))
      })
    })
  }
}

class ExpandManager {
  constructor () {
    this.checkbuttons = [new ExpandPass(), new ExpandFail(), new ExpandIncomplete(), new ExpandCustom()]
  }

  allSelect (selected) {
    localStorage.setItem('expand-all', selected)
    if (selected) {
      document.getElementById('expand-all-icon').classList.remove('fa-circle')
      document.getElementById('expand-all-icon').classList.add('fa-dot-circle')
    } else {
      document.getElementById('expand-all-icon').classList.remove('fa-dot-circle')
      document.getElementById('expand-all-icon').classList.add('fa-circle')
    }
  }

  expandAll () {
    $('.collapsible').collapse('show')
    document.getElementById('expand-all').classList.add('active')
    this.allSelect(true)
  }

  init () {
    for (const i in this.checkbuttons) {
      this.checkbuttons[i].init()
    }

    // check saved preferences
    const expandAllSetting = JSON.parse(localStorage.getItem('expand-all'))

    if (expandAllSetting) {
      this.expandAll()
    }

    // create event handlers
    document.getElementById('expand-all').addEventListener('click', e => {
      if (e.currentTarget.classList.contains('active')) {
        $('.collapsible').collapse('hide')
        e.currentTarget.classList.remove('active')
        this.allSelect(false)
      } else {
        for (const i in this.checkbuttons) {
          this.checkbuttons[i].checkboxSelectCollapse(false)
        }

        this.expandAll()
      }
    })
  }
}

export function initDetail () {
  // check if we are on the right page
  if (!document.getElementById('expand-options')) {
    return
  }

  const expandManager = new ExpandManager()

  const environmentResults = document.getElementById('environment-results')
  // TODO make expand manager part of environment results (use react to update elems instead of vanilla js)
  render(<EnvironmentResults expandManager={expandManager} />, environmentResults)

  const resultSummary = document.getElementById('result-summary')
  render(<DetailedResultSummary />, resultSummary)
}
