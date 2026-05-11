import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from '@/components/common/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { History } from '@/pages/History'
import { Cameras } from '@/pages/Cameras'
import { Config } from '@/pages/Config'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 3000 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="history" element={<History />} />
            <Route path="cameras" element={<Cameras />} />
            <Route path="config" element={<Config />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
