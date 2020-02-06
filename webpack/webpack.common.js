const path = require('path');
const webpack = require('webpack');

module.exports = {
  entry: path.resolve(__dirname, '../cisite/dashboard/js/main.js'),
  output: {
    path: path.resolve(__dirname, '../cisite/dashboard/static/build'),
    filename: 'app.bundle.js',
    chunkFilename: 'vendor.bundle.js',
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        loader: 'babel-loader',
        exclude: /node_modules/,
        query: {
          presets: [
            [
              '@babel/preset-env', {
                useBuiltIns: 'usage',
                corejs: '^3.2.1',
                targets: {
                  browsers: ['last 2 versions']
                }
              }
            ]
          ],
          plugins: [
            [
              '@babel/transform-react-jsx',
              { pragma: 'h' }
            ]
          ]
        }
      }
    ]
  },
  optimization: {
    splitChunks: {
      chunks: 'all',
    },
  },
};
