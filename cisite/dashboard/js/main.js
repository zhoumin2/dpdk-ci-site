import { initDashboard } from './dashboard'
import { initTarballs } from './tarballs'
import { initSubscriptionManager } from './subscriptions'
import { initCIStatus } from './ci_status'
import { initDetail } from './detail'

window.onload = () => {
  initDashboard()
  initTarballs()
  initSubscriptionManager()
  initCIStatus()
  initDetail()
}
