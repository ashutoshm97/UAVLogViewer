// router/index.js

import Vue from 'vue'
import Router from 'vue-router'
// import HelloWorld from '@/components/HelloWorld'
import Home from '../../src/components/Home.vue'
import PlotlyPopup from '../../src/components/PlotlyPopup.vue'
// import AgentView from '../views/AgentView.vue' // <-- 1. ADD THIS IMPORT
import FlightAgentChat from '../components/FlightAgentChat.vue'

Vue.use(Router)

export default new Router({
    routes: [
        {
            path: '/',
            name: 'Home',
            component: Home
        },
        {
            path: '/plot',
            name: 'Plot',
            component: PlotlyPopup
        },
        {
            path: '/v/:id',
            name: 'View',
            component: Home
        },
        // v-- 2. ADD THIS NEW ROUTE OBJECT --v
        {
            path: '/agent',
            name: 'Agent',
            component: FlightAgentChat
        }
    ]
})
