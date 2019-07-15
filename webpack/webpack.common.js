const path = require('path');
const webpack = require('webpack');

module.exports = {
  entry: path.resolve(__dirname, '../cisite/dashboard/js/main.js'),
  output: {
    path: path.resolve(__dirname, '../cisite/dashboard/static/build'),
    filename: 'app.bundle.js'
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        loader: 'babel-loader',
        query: {
          presets: [
            [
              "@babel/preset-env",
            ],
          ]
        }
      }
    ]
  }
};
