import { initDashboard } from './dashboard'
import { initTarballs } from './tarballs'
import { initSubscriptionManager } from './subscriptions'

window.onload = () => {
  initDashboard()
  initTarballs()
  initSubscriptionManager()
}
