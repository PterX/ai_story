const path = require('path');
const webpack = require('webpack');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { VueLoaderPlugin } = require('vue-loader');

const normalizeBasePath = (value = '/') => {
  if (!value || value === '/') {
    return '/';
  }
  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`;
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`;
};

const appBasePath = normalizeBasePath(process.env.APP_BASE_PATH || process.env.BASE_URL || '/');
const sseBaseUrl = Object.prototype.hasOwnProperty.call(process.env, 'VUE_APP_SSE_BASE_URL')
  ? process.env.VUE_APP_SSE_BASE_URL
  : 'http://localhost:8010';

module.exports = {
  entry: {
    app: './src/main.js',
  },
  output: {
    path: path.resolve(__dirname, '../../dist'),
    filename: 'js/[name].[contenthash:8].js',
    clean: true,
    publicPath: appBasePath,
  },
  resolve: {
    extensions: ['.js', '.vue', '.json'],
    alias: {
      '@': path.resolve(__dirname, '../src'),
      'vue$': 'vue/dist/vue.esm.js',
    },
  },
  module: {
    rules: [
      {
        test: /\.vue$/,
        loader: 'vue-loader',
      },
      {
        test: /\.js$/,
        loader: 'babel-loader',
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: [
          'vue-style-loader',
          'css-loader',
          'postcss-loader',
        ],
      },
      {
        test: /\.(png|jpe?g|gif|svg)$/i,
        type: 'asset',
        parser: {
          dataUrlCondition: {
            maxSize: 8 * 1024, // 8kb
          },
        },
        generator: {
          filename: 'images/[name].[hash:8][ext]',
        },
      },
      {
        test: /\.(woff2?|eot|ttf|otf)$/i,
        type: 'asset/resource',
        generator: {
          filename: 'fonts/[name].[hash:8][ext]',
        },
      },
    ],
  },
  plugins: [
    new VueLoaderPlugin(),
    new HtmlWebpackPlugin({
      template: './public/index.html',
      favicon: './public/favicon.ico',
      inject: true,
    }),
    // 定义环境变量，使其在浏览器环境中可用
    new webpack.DefinePlugin({
      'process.env': {
        NODE_ENV: JSON.stringify(process.env.NODE_ENV || 'development'),
        BASE_URL: JSON.stringify(appBasePath),
        VUE_APP_API_BASE_URL: JSON.stringify(process.env.VUE_APP_API_BASE_URL || '/api/v1'),
        VUE_APP_SSE_BASE_URL: JSON.stringify(sseBaseUrl),
        VUE_APP_API_URL: JSON.stringify(process.env.VUE_APP_API_URL || 'http://localhost:8000'),
        VUE_APP_WS_URL: JSON.stringify(process.env.VUE_APP_WS_URL || 'ws://localhost:8000'),
      },
    }),
  ],
};
