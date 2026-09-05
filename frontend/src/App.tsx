import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Chat } from './pages/Chat'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

/**
 * One screen. `/` is the same screen with no case open, so there is no landing
 * page to get past and nothing to navigate — D25.
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/c/:caseId" element={<Chat />} />
          <Route path="*" element={<Chat />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
