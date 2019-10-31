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
  if (!document.getElementById('expand-options')) {
    return
  }

  const expandManager = new ExpandManager()
  expandManager.init()
}
