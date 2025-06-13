<template>
    <div id="app">
      <div class="breadcrumb-nav">
        <router-link to="/">Home / Plotter</router-link>
        <span>|</span>
        <router-link to="/agent">Flight Agent</router-link>
      </div>

      <router-view />
    </div>
  </template>

<script>
export default {
    name: 'App'
}
</script>

  <style>
  @import url('https://fonts.googleapis.com/css?family=Nunito+Sans&display=swap');

  #app {
    font-family: 'Nunito Sans', sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    height: 100%;
    background-color: white;
  }

  html,
  body {
    overscroll-behavior-y: contain;
    margin: 0;
    padding: 0;
    background-color: white;
  }

  /* 🌐 Breadcrumb Navigation Styling */
  .breadcrumb-nav {
    padding: 10px;
    background-color: #085ac5; /* Arena-inspired blue */
    border-bottom: 1px solid #ddd;
    text-align: center;
    font-size: 16px;
    color: white;
  }

  .breadcrumb-nav a {
    color: white;
    text-decoration: none;
    font-weight: 500;
    margin: 0 6px;
    transition: color 0.2s ease;
  }

  .breadcrumb-nav a:hover {
    color: #cce2ff;
  }

  .breadcrumb-nav span {
    color: #d0d0d0;
    margin: 0 4px;
  }
  </style>
