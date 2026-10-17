import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { obtenerAvatar, obtenerPtw } from '../api'
import { AvatarGemelo } from '../componentes/AvatarGemelo'
import { TRABAJADORES } from '../mocks/datos'
import type { Ptw } from '../tipos'
import Admin from '../vistas/Admin'
import { DetalleCaso } from '../vistas/Supervisor'
import { renderizar } from './render'
import { servidor } from './setup'

// Lo que un backend mal configurado podría filtrar desde la zona clínica.
const CLINICO = 'Hipoxemia crónica leve'
const PRESION = '150/95 mmHg'

const ptwConFiltracion = {
  ptw_id: 'PTW-FUGA01',
  estado: 'en_revision',
  solicitud: {
    tarea: 'perforación de frente',
    labor: 'NV-3820 TJ-12',
    turno: 'noche',
    trabajador_id: 'T-001',
    altitud_msnm: 4210,
    tipo_mineria: 'subterranea',
    empleador: 'contratista',
  },
  consultas: {
    incidentes: {
      estado: 'ok',
      data: {
        casos_similares: 3,
        patron: '3 casos similares, 3 de desprendimiento de roca en frente avance durante el turno noche.',
        riesgo_potencial_max: 'alto',
        casos: [{ id: 'INC-0007', resumen_es: 'Desprendimiento de roca del techo.', riesgo_critico: 'desprendimiento_de_roca', causa_probable: 'Desatado insuficiente.' }],
      },
    },
    area: {
      estado: 'ok',
      data: { labor: 'NV-3820 TJ-12', co_ppm: 12, o2_pct: 20.1, ventilacion: 'operativa', ruido_dBA: 91, ultimo_desatado_h: 26 },
    },
    gemelo: {
      estado: 'ok',
      data: {
        trabajador_id: 'T-001',
        apto_para_tarea: 'apto_con_observaciones',
        motivo_visible: 'Descanso por debajo del umbral recomendado.',
        diagnostico: CLINICO,
        presion_arterial: PRESION,
      },
    },
  },
  nanda: [],
  propuesta: {
    decision: 'autorizar_con_controles',
    nivel: 'ambar',
    requiere_supervisor: false,
    porque: ['Ruido 91 dBA supera el máximo de 85 dBA.', 'Último desatado 26 h supera el máximo de 12 h.'],
    controles_extra: ['Doble protección auditiva (tapones y orejeras) y rotación para limitar la exposición'],
    alternativa: 'Si los controles no pueden aplicarse antes del inicio, reprogramar la tarea o reasignarla.',
  },
  explicacion: 'Nivel ámbar: autorizar con controles por desatado pendiente y ruido.',
}

const avatarConFiltracion = {
  ...TRABAJADORES['T-001'],
  diagnostico: CLINICO,
  estado_visual: { ...TRABAJADORES['T-001'].estado_visual, diagnostico: CLINICO, presion_arterial: PRESION },
}

function filtrarTodo() {
  servidor.use(
    http.get('*/ptw/PTW-FUGA01', () => HttpResponse.json(ptwConFiltracion)),
    http.get('*/trabajadores/:id/avatar', () => HttpResponse.json(avatarConFiltracion)),
  )
}

const sinDatosClinicos = (html: string) => {
  expect(html).not.toContain(CLINICO)
  expect(html).not.toContain(PRESION)
}

describe('diagnostico nunca se renderiza', () => {
  it('el cliente de la API descarta el diagnóstico y los campos clínicos del gemelo', async () => {
    filtrarTodo()
    const ptw: Ptw = await obtenerPtw('PTW-FUGA01')
    expect(ptw.consultas.gemelo.data).toEqual({
      trabajador_id: 'T-001',
      apto_para_tarea: 'apto_con_observaciones',
      motivo_visible: 'Descanso por debajo del umbral recomendado.',
      diagnostico: null,
    })
    expect(ptw.consultas.gemelo.diagnostico_descartado).toBe(true)
  })

  it('el monitor muestra diagnostico: null y avisa que descartó el dato clínico', async () => {
    filtrarTodo()
    const { container } = renderizar(<Admin />, '/admin?ptw=PTW-FUGA01')
    await screen.findByText(/Vigía lo descartó sin mostrarlo/)
    expect(container.textContent).toContain('"diagnostico": null')
    sinDatosClinicos(container.innerHTML)
  })

  it('el monitor certifica diagnostico: null cuando el gemelo responde bien', async () => {
    servidor.use(
      http.get('*/ptw/PTW-FUGA01', () =>
        HttpResponse.json({
          ...ptwConFiltracion,
          consultas: {
            ...ptwConFiltracion.consultas,
            gemelo: { estado: 'ok', data: { ...ptwConFiltracion.consultas.gemelo.data, diagnostico: null, presion_arterial: undefined } },
          },
        }),
      ),
    )
    renderizar(<Admin />, '/admin?ptw=PTW-FUGA01')
    await screen.findByText(/El gemelo respondió diagnostico: null/)
  })

  it('el detalle del supervisor no muestra datos clínicos', async () => {
    filtrarTodo()
    const { container } = renderizar(<DetalleCaso ptwId="PTW-FUGA01" />)
    await screen.findByText('Por qué llegó aquí')
    await screen.findByRole('img', { name: /Juan Mamani/ })
    sinDatosClinicos(container.innerHTML)
  })
})

describe('el avatar no muestra datos clínicos', () => {
  it('descarta campos clínicos del endpoint de avatar', async () => {
    filtrarTodo()
    const avatar = await obtenerAvatar('T-001')
    expect(JSON.stringify(avatar)).not.toContain(CLINICO)
    expect(Object.keys(avatar.estado_visual).sort()).toEqual(
      ['apto_para_tarea', 'dia_rotacion', 'energia', 'exposicion_nivel', 'historial_energia', 'motivo_visible', 'total_rotacion'],
    )
  })

  it.each(['sm', 'md', 'lg'] as const)('tamaño %s: texto, aria-label y atributos sin datos clínicos', async (size) => {
    filtrarTodo()
    const { container } = renderizar(<AvatarGemelo trabajadorId="T-001" size={size} />)
    const img = await screen.findByRole('img', { name: /Juan Mamani: Apto con observaciones/ })
    expect(img.getAttribute('aria-label')).toContain('Descanso por debajo del umbral recomendado')
    sinDatosClinicos(container.innerHTML)
  })

  it('muestra el estado con texto, no solo con color', async () => {
    renderizar(<AvatarGemelo trabajadorId="T-001" size="md" />)
    await screen.findByText('Apto con observaciones')
    expect(screen.getByText('Día 12 de 14')).toBeTruthy()
    expect(screen.getByText('Exposición: alta')).toBeTruthy()
  })
})

describe('sin fugas en la demo', () => {
  it('los casos de la demo responden diagnostico: null', async () => {
    const ptw = await obtenerPtw('PTW-SEED-08')
    expect(ptw.consultas.gemelo.diagnostico_descartado).toBe(false)
  })
})

describe('cadena de confianza NANDA en el monitor', () => {
  it('muestra quién certificó a cada agente, la respuesta firmada y por qué descartó al revocado', async () => {
    servidor.use(
      http.get('*/ptw/PTW-FUGA01', () =>
        HttpResponse.json({
          ...ptwConFiltracion,
          consultas: {
            ...ptwConFiltracion.consultas,
            area: { estado: 'error' },
            gemelo: {
              ...ptwConFiltracion.consultas.gemelo,
              evidencia: { nonce: 'n-1', sha256: 'abcdef1234567890', firma: 'f', clave_publica: 'k' },
            },
          },
          nanda: [
            { id: 'vigia-gemelo', capabilities: ['aptitud'], firma: 'valida',
              emisores: ['vigia-salud-ocupacional', 'vigia-sso'], credencial_vence: '2026-10-24T00:00:00+00:00', motivo: null },
            { id: 'vigia-area', capabilities: ['condiciones'], firma: 'invalida',
              emisores: ['vigia-sso'], credencial_vence: null, motivo: 'credencial revocada por la autoridad' },
          ],
        }),
      ),
    )
    const { container } = renderizar(<Admin />, '/admin?ptw=PTW-FUGA01')

    await screen.findByText(/Credencial vigente de Salud Ocupacional y SSO/)
    screen.getByText(/Agente descartado: credencial revocada por la autoridad/)
    screen.getByText(/Firmada por el agente certificado \(sha256 abcdef123456…\)/)
    sinDatosClinicos(container.innerHTML)
  })
})
