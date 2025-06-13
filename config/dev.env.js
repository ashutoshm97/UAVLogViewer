'use strict'
const { merge } = require('webpack-merge')
const prodEnv = require('./prod.env')

module.exports = merge(prodEnv, {
  NODE_ENV: '"development"',
  VUE_APP_CESIUM_TOKEN: JSON.stringify(process.env.VUE_APP_CESIUM_TOKEN || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJiNGRkZTRmMy00ODRlLTRhOWYtYWI4NC0wNDc3MmEwMjFjNDAiLCJpZCI6MzEwMTYxLCJpYXQiOjE3NDk1MTEwNDh9.5iNkluLMkGTozHLh1TjCbbVpT8zMnxlwIdtpySZ56-Q')
})
