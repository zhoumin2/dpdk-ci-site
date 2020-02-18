// All + "Everything else" = radio
// "Everything else" = checkbox
// "Custom" checkbox: allows users to always expand specific environments.
// Since that can include pass/fail/incomplete, then special checks are
// in place to make sure collapsing custom selected environments doesn't
// also collapse pass/fail/incomplete and vice-versa.
import Testrun from './components/Testrun'
import { Component, h, render } from 'preact'

export class GetAllJobs extends Component {
  constructor (props) {
    super(props)
    const sitestatus = document.getElementById('testing')
    const isAdmin = sitestatus.dataset.admin === 'True'
    console.log("startttttttttttttt")
    this.state = {
      environments: {},
      testcases: {},
      isAdmin: isAdmin
    }
  }

  componentDidMount () {
    console.log(5)
    const sitestatus = document.getElementById('testing')
    const jobs = sitestatus.dataset.environments
    console.log(sitestatus.dataset)
    console.log(sitestatus.dataset.environments)

    fetch("?environments="+jobs).then(res => {
      if (res.ok) {
        return res.json()
      }
    }).then(json => {
      this.setState(state => {
      console.log(json)
      console.log(state)
        return json
      })
    })
  }

  render () {
    return (
    <div>{(Object.keys(this.state.environments).length !== 0 &&
      <div>{Object.values(this.state.environments).map((environment) =>
        <div class="card mb-3" id={`accordion-${environment.id}`}>
          <button class="card-header d-flex justify-content-between align-items-center btn text-left" data-toggle="collapse" data-target={`#collapse-${environment.id}`} aria-expanded="false" aria-controls={`collapse-${environment.id}`}>
            <h3 class="mb-0 env-title" id={`env-${environment.id}`}>{ environment.name }</h3>
            <div class="text-nowrap">
              {!environment.live_since  &&
                  <span class="text-secondary fas fa-minus-circle" title="This run does not affect the overall result above."></span>
              }

              {(environment.all_pass &&
                  <span class="text-success fas fa-check-circle" title="All test cases passed"></span>
              ) || (environment.all_pass === false &&
                  <span class="text-danger fas fa-times-circle" title="At least one test case did not pass"></span>
              ) || (
                  <span class="text-secondary fas fa-circle" title="There are not yet any runs for this patch set"></span>
              )}
            </div>
          </button>
          <div id={`collapse-${environment.id}`} class="collapse collapsible" aria-labelledby={`env-${environment.id}`} data-parent={`#accordion-${environment.id}`} data-all-pass="{ environment.all_pass }">
            <div class="card-body">
                {( environment.hardware_description &&
                    <h4><a href="{ environment.hardware_description }">Configuration Information</a></h4>
                ) || (
                    <h4>Configuration Information</h4>
                )}

              <dl class="row">
                <dt class="col-sm-3 col-lg-2">Kernel</dt>
                <dd class="col-sm-9 col-lg-10">{ environment.kernel_name } { environment.kernel_version }</dd>

                <dt class="col-sm-3 col-lg-2">Compiler</dt>
                <dd class="col-sm-9 col-lg-10">{ environment.compiler_name } { environment.compiler_version }</dd>
              </dl>

              {(this.state.isAdmin && environment.pipeline && tarball &&
                <form class="form-inline" action="{% url 'dashboard_build' tarball.id %}?next={ request.get_full_path }" method="POST">
                  <input type="hidden" name="csrfmiddlewaretoken" value={this.state.csrf}/>
                  <label class="mr-2" for="pipeline-select" title="Used for initially running a test in case it could not be ran automatically">Run pipeline</label>
                  <select id="pipeline-select" class="form-control form-control-sm mr-2 mb-2 mb-sm-0" name="pipeline">
                    {Object.keys(this.state.testcases).map(testcase => {
                      {(testcase.pipeline &&
                        <option value="{ testcase.pipeline }-{ environment.pipeline }">{ testcase.name }</option>
                      )}
                    })}
                  </select>
                  <input type="submit" class="btn btn-sm btn-warning" value="Build"/>
                </form>
              )}
                {environment.testcases && Object.values(environment.testcases).map((tc, index) => {
                  {(tc.runs.length > 1 &&
                    <div class="card mt-3">
test
                      <div class="card-header">
                        <div class="d-flex flex-column justify-content-lg-between flex-lg-row">
                          <h4 class="mb-lg-0">
                            {(tc.description_url &&
                              <a href="{ tc.description_url }">{ tc.name }</a>
                            ) || (
                              <div>{ tc.name }</div>
                            )}
                          </h4>
                          <ul class="nav nav-tabs card-header-tabs ml-2">
                            {tc.runs.map(r => (
                              <li class="nav-item">
                                <a class="nav-link{ forloop.first|yesno:' active,' }" data-toggle="tab" href="#run-{ r.id }" role="tab" aria-controls="run-{ r.id }" aria-selected="{ forloop.first|lower }">
                                     Run { environment.testcases.length - index }
                                </a>
                              </li>
                             ))}
                          </ul>
                        </div>
                      </div>
                      <div class="card-body">
                        <div class="tab-content">
                        {tc.runs.map(r => (
                          <div class="tab-pane fade{ forloop.first|yesno:' show active,' }" id="run-{ r.id }" role="tabpanel" aria-labelledby="run-{ r.id }-tab">
                          <Testrun r={tc.runs[0]}></Testrun>
                          </div>
                        ))}
                        </div>
                      </div>
                    </div>
                  )|| (tc.runs.length == 1 &&
                    <div class="card mt-3">
                      <h4 class="card-header">
                        {(tc.description_url &&
                            <a href="{ tc.description_url }">{ tc.name }</a>
                        ) || (
                            <div>{ tc.name }</div>
                        )}
                      </h4>
                      <div class="card-body">
                          <Testrun r={tc.runs[0]}></Testrun>
                      </div>
                    </div>
                  )}
                })}
            </div>
          </div>
        </div>
      )} </div>
      ) || (
        <p>
            There are not yet any runs for this patch set or you do not have
            permission to view detailed results for any test runs for this patch
            set.
        </p>
      )}</div>
    )
  }
}

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
    this.selector = '.collapsible[data-all-pass="True"]'
    this.inverseSelector = '.collapsible:not([data-all-pass="True"])'
  }
}

class ExpandFail extends Expander {
  constructor () {
    super()
    this.button = document.getElementById('expand-fail')
    this.icon = document.getElementById('expand-fail-icon')
    this.setting = 'expand-fail'
    this.selector = '.collapsible[data-all-pass="False"]'
    this.inverseSelector = '.collapsible:not([data-all-pass="False"])'
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
    this.customConflictSelectors = ['True', 'False', '']
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
        // don't bubble events if clicking on anchorjs
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
  const domContainer = document.getElementById('expand-options')
  console.log(1)
  const testingc = document.getElementById('testing')
  if (!domContainer) {
    return
  }
  render(<GetAllJobs />, testingc)
  console.log(2)
  const expandManager = new ExpandManager()
  expandManager.init()

}
