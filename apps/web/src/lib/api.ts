import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export const api = {
  // Venues
  getVenues: () => http.get('/venues').then(r => r.data),
  createVenue: (data: { name: string; width: number; height: number }) =>
    http.post('/venues', data).then(r => r.data),
  getVenue: (id: number) => http.get(`/venues/${id}`).then(r => r.data),
  deleteVenue: (id: number) => http.delete(`/venues/${id}`),

  // Layouts
  uploadLayout: (form: FormData) =>
    http.post('/layouts/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data),
  getLayout: (id: number) => http.get(`/layouts/${id}`).then(r => r.data),
  getLayoutSimruns: (id: number) => http.get(`/layouts/${id}/simruns`).then(r => r.data),
  deleteLayout: (id: number) => http.delete(`/layouts/${id}`),

  // SimRuns
  createSimRun: (layoutId: number, visitorCount: number) =>
    http.post(`/layouts/${layoutId}/simruns`, { visitor_count: visitorCount }).then(r => r.data),
  getSimRun: (id: number) => http.get(`/simruns/${id}`).then(r => r.data),
  compareSimRuns: (a: number, b: number) =>
    http.get('/simruns/compare', { params: { a, b } }).then(r => r.data),

  // Scans
  uploadScan: (form: FormData) =>
    http.post('/scan/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data),
  getScan: (id: number) => http.get(`/scan/${id}`).then(r => r.data),
}
