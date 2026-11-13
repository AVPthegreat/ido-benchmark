  kRequestCacheValidateFns,
  kRequestContentType,
  kRouteContext,
  kRequestOriginalUrl,
  kRequestSignal,
  kOnAbort
} = require('./symbols')
const { FST_ERR_REQ_INVALID_VALIDATION_INVOCATION, FST_ERR_DEC_UNDECLARED } = require('./errors')
const decorators = require('./decorate')
const ContentType = require('./content-type')

const HTTP_PART_SYMBOL_MAP = {
  body: kSchemaBody,
  headers: kSchemaHeaders,
  params: kSchemaParams,
  querystring: kSchemaQuerystring,
  query: kSchemaQuerystring
}

function Request (id, params, req, query, log, context) {
  this.id = id
  this[kRouteContext] = context
  this.params = params
  this.raw = req
  this.query = query
  this.log = log
  this.body = undefined
}
Request.props = []
Request.instanceProperties = new Set(['id', 'params', 'raw', 'query', 'log', 'body'])

function getTrustProxyFn (tp) {
  if (typeof tp === 'function') {
    return tp
  }
  if (tp === true) {
    // Support trusting everything
    return function () { return true }
  }
  if (typeof tp === 'number') {
    // Support trusting hop count
    return function (a, i) { return i < tp }
  }
  if (typeof tp === 'string') {
    // Support comma-separated tps
    const values = tp.split(',').map(it => it.trim())
    return proxyAddr.compile(values)
  }
  return proxyAddr.compile(tp)
}

function buildRequest (R, trustProxy) {
  if (trustProxy) {
    return buildRequestWithTrustProxy(R, trustProxy)
  }

  return buildRegularRequest(R)
}

function buildRegularRequest (R) {
  const props = R.props.slice()
  function _Request (id, params, req, query, log, context) {
    this.id = id
    this[kRouteContext] = context
    this.params = params
    this.raw = req
    this.query = query
    this.log = log
    this.body = undefined

    let prop
    for (let i = 0; i < props.length; i++) {
      prop = props[i]
      this[prop.key] = prop.value
    }
  }
  Object.setPrototypeOf(_Request.prototype, R.prototype)
  Object.setPrototypeOf(_Request, R)
  _Request.props = props
  _Request.parent = R

  return _Request
