import assert from 'node:assert/strict'
import test from 'node:test'
import * as THREE from 'three'

import { localMovementDirection } from '../src/firstPerson.js'

function rounded(vector) {
  return vector.toArray().map((value) => Math.round(value * 1e6) / 1e6)
}

test('W/S move along camera forward while A/D strafe without rotation', () => {
  const facingNorth = new THREE.Vector3(0, 0, -1)
  assert.deepEqual(rounded(localMovementDirection(facingNorth, new Set(['forward']))), [0, 0, -1])
  assert.deepEqual(rounded(localMovementDirection(facingNorth, new Set(['backward']))), [0, 0, 1])
  assert.deepEqual(rounded(localMovementDirection(facingNorth, new Set(['left']))), [-1, 0, 0])
  assert.deepEqual(rounded(localMovementDirection(facingNorth, new Set(['right']))), [1, 0, 0])
})

test('diagonal planar movement is normalized and follows camera yaw', () => {
  const facingEast = new THREE.Vector3(1, 0.4, 0)
  const movement = localMovementDirection(facingEast, new Set(['forward', 'right']))
  assert.ok(Math.abs(movement.length() - 1) < 1e-8)
  assert.deepEqual(rounded(movement), [0.707107, 0, 0.707107])
})
