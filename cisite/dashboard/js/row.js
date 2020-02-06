import { Component } from 'preact'
import { isPageChange } from './utils'

export class Row extends Component {
  /**
   * This is not really the correct usage for a component, but this does
   * exactly what I need it to do. (Which is to share common methods and state
   * for different components.)
   */
  constructor (props, type, linkStart, linkEnd, shown, isAdmin) {
    super(props)

    this.type = type
    this.linkStart = linkStart
    this.linkEnd = linkEnd
    this.shown = shown
    this.isAdmin = isAdmin

    this.errorStatus = {
      status: 'Error getting status',
      incomplete: 0,
      testcases: {}
    }

    const rows = []
    for (let i = linkStart; i < linkEnd; i++) {
      rows.push({ js_id: i })
    }

    this.state = {
      rows: rows
    }
  }

  componentDidMount () {
    const tableSize = this.linkEnd - this.linkStart
    this.getAndAddRow(this.linkStart, tableSize, this.shown)
  }

  setRowState (to, rows) {
    for (let i = 0; i < to; i++) {
      this.setState(state => {
        state.rows[i] = rows[i]
        return { rows: state.rows }
      })

      // only call if the series was not set from cache
      if (!rows[i].series && rows[i].series_id) {
        this.setSeries(rows, i)
      }

      this.setResultSummary(rows, i)
    }
  }

  setSeries (rows, i) {
    fetch(`row/${rows[i].id}/?series=${rows[i].series_id}`).then(response => {
      if (response.ok) {
        return response.json()
      } else {
        response.text().then(text => {
          this.setState(state => {
            state.rows[i].error = `Error getting patchwork information: ${text}`
            return { rows: state.rows }
          })
          logError(response)
        })
      }
    }).then(json => {
      this.setState(state => {
        state.rows[i].series = json
        return { rows: state.rows }
      })
    }).catch(e => {
      let text = `Error getting patchwork information: ${e}`
      if (!isPageChange(e)) {
        logError(e)
      } else {
        text = ''
      }

      this.setState(state => {
        state.rows[i].error = text
        return { rows: state.rows }
      })
    })
  }

  setResultSummary (rows, i) {
    fetch(`row/${rows[i].id}/?result_summary=True`).then(response => {
      if (response.ok) {
        return response.json()
      } else {
        response.text(() => {
          this.setState(state => {
            state.rows[i].result_summary = this.errorStatus
            return { rows: state.rows }
          })
          logError(response)
        })
      }
    }).then(json => {
      this.setState(state => {
        state.rows[i].result_summary = json
        return { rows: state.rows }
      })
    }).catch(e => {
      if (!isPageChange(e)) {
        logError(e)
      }

      this.setState(state => {
        state.rows[i].result_summary = this.errorStatus
        return { rows: state.rows }
      })
    })
  }

  /**
   * Fetch the row from the server, and replace the placeholders
   */
  getAndAddRow (linkOffset, tableSize, shown) {
    fetch(`row/${linkOffset}/?${this.type}=${shown}`).then(response => {
      if (response.ok) {
        return response.json()
      } else {
        response.text().then(text => {
          for (let i = 0; i < tableSize; i++) {
            this.setState(state => {
              state.rows[i].error = `Error getting patch information: ${text}`
              return { rows: state.rows }
            })
          }
          logError(response)
        })
      }
    }).then(json => {
      const rows = json[this.type]

      if (rows.length === tableSize) {
        // normal case
        this.setRowState(rows.length, rows)
      } else if (rows.length > tableSize) {
        // new rows added by the time of requesting
        this.setRowState(tableSize, rows)
      } else {
        // old rows removed by the time of requesting
        this.setRowState(rows.length, rows)
        const rest = tableSize - rows.length

        for (let i = rows.length; i < rest; i++) {
          this.setState(state => {
            state.rows[i].error = 'A patch may have become inactive at the time of requesting.'
            return { rows: state.rows }
          })
        }
      }
    }).catch(e => {
      let text = `Error getting information: ${e}`
      if (isPageChange(e)) {
        text = ''
      } else {
        logError(e)
      }

      for (let i = 0; i < this.state.rows.length; i++) {
        this.setState(state => {
          state.rows[i].error = text
          return { rows: state.rows }
        })
      }
    })
  }
}
