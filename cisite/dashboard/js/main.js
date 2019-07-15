import { Dashboard } from "./dashboard";
import { SubscriptionManager } from "./subscriptions";

window.onload = () => {
  new Dashboard();
  new SubscriptionManager();
}
