module.exports = {
  env: {
    browser: true,
    es6: true,
    jquery: true
  },
  extends: [
    'standard'
  ],
  globals: {
    Atomics: 'readonly',
    SharedArrayBuffer: 'readonly',
    logError: 'readonly',
    toastr: 'readonly'
  },
  parser: 'babel-eslint',
  parserOptions: {
    ecmaFeatures: {
      jsx: true
    },
    ecmaVersion: 2018,
    sourceType: 'module'
  },
  plugins: [
    'react'
  ],
  rules: {
   'react/jsx-uses-vars': [2],
   'no-unused-vars': ['error', { 'varsIgnorePattern': 'h' }]
  }
}
