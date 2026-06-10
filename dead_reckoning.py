import numpy as np
import quaternion

class deadReckoning:
    default_acceleration = np.array([0.0, 0.0, 9.81]) # ax, ay, az, global

    def __init__(self):
        self.position = np.array([0.0, 0.0, 0.0]) # x, y, z, global
        self.velocity = np.array([0.0, 0.0, 0.0]) # vx, vy, vz, global
        self.acceleration = np.array([0.0, 0.0, 0.0]) # ax, ay, az, global
        self.quaternion = quaternion.one

        self.prev_position = np.array([0.0, 0.0, 0.0]) # x, y, z, global
        self.prev_velocity = np.array([0.0, 0.0, 0.0]) # vx, vy, vz, global
        self.prev_acceleration = np.array([0.0, 0.0, 0.0]) # ax, ay, az, global
        self.prev_quaternion = quaternion.one
    
    def update(self, data, dt):
        local_acceleration = np.array([data["linear acceleration"]["x"], data["linear acceleration"]["y"], data["linear acceleration"]["z"]])
        local_omega = np.array([data["angular rates"]["x"], data["angular rates"]["y"], data["angular rates"]["z"]])

        rotation = quaternion.from_rotation_vector(local_omega * dt)
        self.quaternion = 0.5*(self.quaternion + self.prev_quaternion) * rotation
        self.acceleration = quaternion.rotate_vectors(rotation, local_acceleration) - self.default_acceleration
        self.velocity += 0.5*(self.acceleration + self.prev_acceleration) * dt
        self.position += 0.5*(self.velocity + self.prev_velocity) * dt
        self.angle += local_omega * dt

        self.prev_position = self.position.copy()
        self.prev_velocity = self.velocity.copy()
        self.prev_acceleration = self.acceleration.copy()
        self.prev_quaternion = self.quaternion.copy()