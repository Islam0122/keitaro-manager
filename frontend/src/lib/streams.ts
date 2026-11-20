import type { StreamSchema, StreamType } from '@/types/api'

export const STREAM_TYPES: Record<StreamType, string> = {
  forced: 'Перехватывающий (forced)',
  regular: 'Обычный (regular)',
  default: 'Запасной (default)',
}

export const STREAM_SCHEMAS: Record<StreamSchema, string> = {
  redirect: 'Редирект на URL',
  landings: 'Офферы',
  action: 'Действие',
}

export const REDIRECT_ACTIONS: Record<string, string> = {
  http: 'HTTP-редирект (302)',
  meta: 'Meta refresh',
  double_meta: 'Double meta refresh',
  js: 'JavaScript-редирект',
  blank_referrer: 'Без реферера',
  frame: 'Frame',
  iframe: 'iFrame',
  curl: 'CURL',
  remote: 'Remote',
  formsubmit: 'Form submit',
}

export const OTHER_ACTIONS: Record<string, string> = {
  status404: 'Ответ 404',
  show_text: 'Показать текст',
  show_html: 'Показать HTML',
  do_nothing: 'Ничего не делать',
}

/** Keitaro stream filters whose payload is a list of strings. */
export const LIST_FILTERS: Record<string, string> = {
  region: 'Регион',
  city: 'Город',
  language: 'Язык браузера',
  browser: 'Браузер',
  os: 'ОС',
  device_type: 'Тип устройства',
  ip: 'IP / диапазон',
  isp: 'Провайдер (ISP)',
  operator: 'Мобильный оператор',
  connection_type: 'Тип соединения',
  referrer: 'Реферер',
  keyword: 'Ключевое слово',
  user_agent: 'User Agent',
}

export function filterLabel(name: string): string {
  if (name === 'country') return 'Страна'
  return LIST_FILTERS[name] ?? name
}
