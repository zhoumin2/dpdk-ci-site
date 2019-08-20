import { Component } from 'preact'

export class Row extends Component {
  /**
   * This is not really the correct usage for a component, but this does
   * exactly what I need it to do. (Which is to share common methods and state
   * for different components.)
   */
  constructor (props, type, linkStart, linkEnd, limit, shown, isAdmin) {
    super(props)

    this.type = type
    this.linkStart = linkStart
    this.linkEnd = linkEnd
    this.limit = limit
    this.shown = shown
    this.isAdmin = isAdmin

    const rows = []
    for (let i = linkStart; i < linkEnd; i++) {
      // negative id to not conflict with retrieved row id
      rows.push({ id: -i })
    }

    this.state = {
      rows: rows
    }
  }

  componentDidMount () {
    const tableSize = this.linkEnd - this.linkStart
    for (let i = 0; i < tableSize; i += this.limit) {
      this.getAndAddRow(i, i + this.linkStart, this.limit, tableSize, this.shown)
    }
  }

  setRowState (offset, to, rows) {
    for (let i = 0; i < to; i++) {
      this.setState(state => {
        state.rows[i + offset] = rows[i]
        return { rows: state.rows }
      })
    }
  }

  /**
   * Fetch the row from the server, and replace the placeholders
   */
  getAndAddRow (tableOffset, linkOffset, limit, tableSize, shown) {
    // there is a possible race condition where the active rows change after
    // the initial request. This also accounts for when the limit ends up greater
    // than the offset.

    // case 1: offset=4, limit=4, size=16, ret=4 (normal case) (ret + offset < size)
    //         offset=4, limit=4, size=8,  ret=4
    //         offset=1, limit=4, size=5,  ret=4
    //         offset=5, limit=4, size=10, ret=4
    // case 2: offset=4, limit=4, size=7,  ret=4 (ret + offset > size) (size - offset < limit)
    //         offset=4, limit=4, size=5,  ret=4
    // case 3: offset=4, limit=4, size=8,  ret=3 (ret < limit)
    const max = tableSize - tableOffset

    fetch(`row/${linkOffset}/?limit=${limit}&${this.type}=${shown}`).then(response => {
      if (response.ok) {
        return response.json()
      } else {
        response.text(text => {
          for (let i = tableOffset; i < max; i++) {
            this.setState(state => {
              state.rows[i] = { id: i, error: `Error getting patch information: ${text}` }
              return { rows: state.rows }
            })
          }
          logError(response)
        })
      }
    }).then(json => {
      const rows = json[this.type]

      if (rows.length + tableOffset <= tableSize) {
        // case 1
        this.setRowState(tableOffset, rows.length, rows)
      } else if (rows.length + tableOffset > tableSize && rows.length >= limit) {
        // case 2
        this.setRowState(tableOffset, max, rows)
      } else {
        // case 3
        this.setRowState(tableOffset, rows.length, rows)
        const rest = max - rows.length
        for (let i = tableOffset + rows.length; i < rest; i++) {
          this.setState(state => {
            state.rows[i] = { id: i, error: 'This patch may have become inactive at the time of requesting.' }
            return { rows: state.rows }
          })
        }
      }
    }).catch(e => {
      let text = `Error getting patch information: ${e}`
      // Happens when changing pages during a fetch in Firefox. Ignore it.
      if (e.message === 'NetworkError when attempting to fetch resource.') {
        text = ''
      } else {
        logError(e)
      }
      for (let i = 0; i < this.state.rows.length; i++) {
        this.setState(state => {
          state.rows[i] = { id: i, error: text }
          return { rows: state.rows }
        })
      }
    })
  }
}
