import { Routes, Route, Link } from 'react-router-dom'

function Nav() {
  return (
    <nav style={{
      position: 'fixed', top: 0, left: 0, right: 0, height: 48, zIndex: 100,
      background: 'rgba(24,24,21,0.92)', backdropFilter: 'blur(8px)',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      display: 'flex', alignItems: 'center', padding: '0 24px', gap: 32,
    }}>
      <Link to="/" style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--color-primary)', fontSize: 18, textDecoration: 'none' }}>
        로도
      </Link>
      <Link to="/venues" style={{ color: 'var(--color-text-on-canvas)', fontSize: 14, textDecoration: 'none' }}>행사장</Link>
      <Link to="/scan" style={{ color: 'var(--color-text-on-canvas)', fontSize: 14, textDecoration: 'none' }}>3D 스캔</Link>
      <Link to="/compare" style={{ color: 'var(--color-text-on-canvas)', fontSize: 14, textDecoration: 'none' }}>비교</Link>
    </nav>
  )
}

function Placeholder({ title }: { title: string }) {
  return (
    <div style={{ paddingTop: 80, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100dvh', gap: 12 }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--color-text-on-canvas)' }}>{title}</h1>
      <p style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>구현 예정</p>
    </div>
  )
}

export function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<Placeholder title="로도 — 행사장 혼잡 분석" />} />
        <Route path="/venues" element={<Placeholder title="행사장 목록" />} />
        <Route path="/layouts/:id" element={<Placeholder title="배치도 3D 뷰어" />} />
        <Route path="/simruns/:id" element={<Placeholder title="시뮬레이션 결과" />} />
        <Route path="/scan" element={<Placeholder title="3D 공간 스캔" />} />
        <Route path="/scan/:id" element={<Placeholder title="스캔 뷰어" />} />
        <Route path="/compare" element={<Placeholder title="배치안 비교" />} />
      </Routes>
    </>
  )
}
