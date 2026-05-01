import './App.css'
import WelcomePage from './pages/WelcomePage'
import AppPage from './pages/AppPage'

const isWelcome = window.location.pathname.startsWith('/welcome')

export default function App() {
  return isWelcome ? <WelcomePage /> : <AppPage />
}
