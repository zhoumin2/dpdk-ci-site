import { initDashboard } from './dashboard'
import { initTarballs } from './tarballs'
import { initSubscriptionManager } from './subscriptions'
import { initCIStatus } from './ci_status'

window.onload = () => {
  initDashboard()
  initTarballs()
  initSubscriptionManager()
  initCIStatus()
}
